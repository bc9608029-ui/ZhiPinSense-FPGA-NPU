"""Load the frozen 12-class model and produce raw fp32 logits (PyTorch + ONNX).

Fail-closed: the checkpoint SHA-256, the 12-class label order, the output
dimension, and the input shape are all verified before any logits are produced.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ood_u import contract
from models.ad_amr_v1_1_net import ADAMRV11Net


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_checkpoint_dict(checkpoint_path: str | Path) -> dict[str, Any]:
    path = Path(checkpoint_path)
    if not path.is_file():
        raise FileNotFoundError(f"12-class checkpoint missing: {path}")
    actual = sha256_file(path)
    if actual != contract.CHECKPOINT_SHA256:
        raise RuntimeError(
            f"12-class checkpoint SHA-256 mismatch: expected {contract.CHECKPOINT_SHA256}, got {actual}"
        )
    state = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(state, dict) or "model_state" not in state:
        raise RuntimeError("12-class checkpoint is not a valid training payload (missing model_state)")
    return state


def load_model(checkpoint_path: str | Path) -> ADAMRV11Net:
    """Load + verify the frozen 12-class model, returned in eval mode."""
    state = _load_checkpoint_dict(checkpoint_path)

    class_names = [str(v).upper() for v in state.get("class_names", [])]
    contract.assert_12class_order(class_names)

    model = ADAMRV11Net(num_classes=contract.OUTPUT_DIM)
    model.load_state_dict(state["model_state"], strict=True)
    model.eval()
    return model


def to_tensor(planar_iq: np.ndarray) -> torch.Tensor:
    """Planar fp32 [N, 2, L] -> torch fp32 tensor (already RMS-normalized)."""
    arr = np.asarray(planar_iq, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[1] != 2 or arr.shape[2] != contract.SAMPLE_LENGTH:
        raise ValueError(f"expected planar IQ [N,2,{contract.SAMPLE_LENGTH}], got {arr.shape}")
    return torch.from_numpy(arr)


def predict_logits(model: ADAMRV11Net, planar_iq: np.ndarray) -> np.ndarray:
    """Run the fp32 model and return raw logits [N, 12] (no softmax)."""
    tensor = to_tensor(planar_iq)
    with torch.inference_mode():
        logits, _ = model(tensor)
    logits = logits.detach().cpu().numpy().astype(np.float64)
    contract.assert_logits_12(logits)
    return logits


def predict_logits_onnx(onnx_path: str | Path, planar_iq: np.ndarray) -> np.ndarray:
    """Run the fp32 ONNX model and return raw logits [N, 12] (no softmax).

    The exported ONNX graph carries a fixed batch dimension of 1, so each sample
    is fed individually and the [1, 12] outputs are concatenated.
    """
    import onnxruntime as ort

    onnx_path = Path(onnx_path)
    if not onnx_path.is_file():
        raise FileNotFoundError(f"ONNX model missing: {onnx_path}")
    actual = sha256_file(onnx_path)
    if actual != contract.ONNX_SHA256:
        raise RuntimeError(
            f"12-class ONNX SHA-256 mismatch: expected {contract.ONNX_SHA256}, got {actual}"
        )
    arr = np.asarray(planar_iq, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[1] != 2 or arr.shape[2] != contract.SAMPLE_LENGTH:
        raise ValueError(f"expected planar IQ [N,2,{contract.SAMPLE_LENGTH}], got {arr.shape}")
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    rows: list[np.ndarray] = []
    for i in range(arr.shape[0]):
        out = session.run(None, {input_name: arr[i:i + 1]})[0]
        rows.append(np.asarray(out, dtype=np.float64).reshape(1, contract.OUTPUT_DIM))
    logits = np.concatenate(rows, axis=0)
    contract.assert_logits_12(logits)
    return logits


__all__ = ["sha256_file", "load_model", "to_tensor", "predict_logits", "predict_logits_onnx"]
