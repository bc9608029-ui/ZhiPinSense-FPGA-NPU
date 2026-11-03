"""
ptq_quantize.py
===============
Static INT8 post-training quantization for DSC-AMCNet, matching the paper's
deployment pipeline (Section III-B):

    1. ONNX export (fixed batch size 1).
    2. Static INT8 PTQ via onnxruntime.quantization.quantize_static
       with QuantFormat.QDQ and 1,024 calibration samples.
    3. (Downstream) ST Edge AI Core 2.2.0 analyze -> CubeIDE -> flash.

Backend note (see validate_backend.py): the deployed graph must carry
SIGNED INT8 (zero-point 0). Unsigned INT8 (qnnpack-style, zero-point 128)
is incompatible with X-CUBE-AI and fails silently on device.

Expected PTQ result (paper Table II): 86.92% INT8 at +10 dB,
+0.09 pp degradation vs FP32 (87.01%).

Usage:
    python quantization/ptq_quantize.py \
        --checkpoint models/checkpoints/dscamcnet_best.pt \
        --data       datasets/RML2016.10a_dict.dat \
        --split      datasets/split_indices.npz \
        --output     quantization/outputs/dscamcnet_int8.onnx
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent.parent / "models"))
from dsc_amcnet import build_dsc_amcnet, normalize_window  # noqa: E402
from train import load_rml2016, load_split  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent / "models"))

from onnxruntime.quantization import (CalibrationDataReader, QuantFormat,
                                      QuantType, quantize_static)

N_CALIB = 1024  # paper Section III-B


class RMLCalibReader(CalibrationDataReader):
    """Feeds 1,024 L2-normalized training windows to the calibrator."""

    def __init__(self, data_path: str, split_path: str,
                 n_calib: int = N_CALIB, seed: int = 42):
        X, y, _ = load_rml2016(data_path)
        train_idx, _ = load_split(split_path)
        rng = np.random.default_rng(seed)
        pick = rng.choice(train_idx, size=n_calib, replace=False)
        xt = normalize_window(torch.from_numpy(X[pick]).float()).numpy()
        self._it = iter([{"input": xt[i:i + 1]} for i in range(n_calib)])

    def get_next(self):
        return next(self._it, None)


def export_fp32_onnx(checkpoint: str, fp32_path: str,
                     opset: int = 13) -> None:
    """Export the FP32 model to ONNX with fixed batch size 1.

    NOTE: the released Zenodo artifact (dscamcnet_int8.onnx) carries
    opset 13 / IR 8. X-CUBE-AI 10.2 requires IR <= 8; if a newer ONNX
    writes a higher IR, patch model.ir_version = 8 before saving.
    """
    model = build_dsc_amcnet()
    sd = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if isinstance(sd, dict) and "state_dict" in sd:
        sd = sd["state_dict"]
    model.load_state_dict(sd, strict=True)
    model.eval()
    dummy = torch.randn(1, 2, 128)
    torch.onnx.export(model, dummy, fp32_path, opset_version=opset,
                      input_names=["input"], output_names=["logits"],
                      dynamo=False)
    import onnx
    m = onnx.load(fp32_path)
    if m.ir_version > 8:
        m.ir_version = 8
        onnx.save(m, fp32_path)


def main(args):
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    fp32_path = str(out.with_name(out.stem.replace("_int8", "") +
                                  "_fp32.onnx"))

    print(f"[1/3] Exporting FP32 ONNX -> {fp32_path}")
    export_fp32_onnx(args.checkpoint, fp32_path)

    print(f"[2/3] Static PTQ (QDQ, signed INT8, {N_CALIB} calib samples)")
    reader = RMLCalibReader(args.data, args.split)
    quantize_static(
        model_input=fp32_path,
        model_output=str(out),
        calibration_data_reader=reader,
        quant_format=QuantFormat.QDQ,
        activation_type=QuantType.QInt8,
        weight_type=QuantType.QInt8,
    )

    print(f"[3/3] Done -> {out}")
    print("Next: stedgeai analyze --target stm32h7 " + str(out))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="PTQ (QDQ, signed INT8) for "
                                            "DSC-AMCNet")
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--split", required=True)
    p.add_argument("--output",
                   default="quantization/outputs/dscamcnet_int8.onnx")
    main(p.parse_args())
