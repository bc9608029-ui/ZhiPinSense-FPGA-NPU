"""NPU-boundary consistency and direction checks for the M25-B framework.

The 24-class NPU outputs 24 raw logits.  Before any threshold is trusted on the
board, the Energy score and OOD direction must agree across five representations:

  1. PyTorch fp32   (training / reference)
  2. ONNX Runtime fp32
  3. fake-int8       (CPU simulation of the NPU int8 path)
  4. real NPU logits (only present after on-board capture — offline placeholder)
  5. Energy + threshold decision

All imports are lazy so the module compiles and its offline checks run without
torch/onnxruntime installed.  Missing real-NPU logits are reported as
``NPU_LOGITS_MISSING`` (never fabricated).
"""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np

NPU_LOGITS_MISSING = "NPU_LOGITS_MISSING"
BOUNDARY_OK = "M25B_NPU_BOUNDARY_OK"
BOUNDARY_MISMATCH = "M25B_NPU_BOUNDARY_MISMATCH"


def energy_np(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    from ood.m25b_scores import score_energy
    return score_energy(logits, temperature)


def fake_int8_logits(logits: np.ndarray, *, num_bits: int = 8) -> np.ndarray:
    """Simulate the NPU int8 quantization of raw logits (symmetric, per-tensor)."""
    x = np.asarray(logits, dtype=np.float64)
    qmax = 2 ** (num_bits - 1) - 1
    scale = np.max(np.abs(x)) / qmax
    if scale <= 0:
        scale = 1.0
    q = np.clip(np.round(x / scale), -qmax, qmax)
    return (q * scale).astype(np.float64)


def torch_logits(model: Any, x: np.ndarray) -> np.ndarray:
    import torch
    with torch.no_grad():
        t = torch.as_tensor(np.ascontiguousarray(x), dtype=torch.float32)
        out = model(t)
        return out.detach().cpu().numpy().astype(np.float64)


def ort_logits(session: Any, x: np.ndarray) -> np.ndarray:
    input_name = session.get_inputs()[0].name
    out = session.run(None, {input_name: np.ascontiguousarray(x, dtype=np.float32)})
    return np.asarray(out[0], dtype=np.float64)


def compare_logits(a: np.ndarray, b: np.ndarray, *, atol: float = 1e-3,
                   rtol: float = 1e-3) -> dict[str, Any]:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        return {"match": False, "reason": "shape_mismatch",
                "shape_a": a.shape, "shape_b": b.shape}
    close = np.allclose(a, b, atol=atol, rtol=rtol)
    max_abs = float(np.max(np.abs(a - b)))
    same_argmax = bool(np.argmax(a) == np.argmax(b))
    return {"match": close, "max_abs_diff": max_abs, "same_argmax": same_argmax}


def energy_direction_consistent(logits_a: np.ndarray, logits_b: np.ndarray,
                                temperature: float = 1.0) -> dict[str, Any]:
    """Both representations must rank a shared batch's Energy the same way."""
    ea = energy_np(logits_a, temperature)
    eb = energy_np(logits_b, temperature)
    a_rank = np.argsort(np.argsort(ea))
    b_rank = np.argsort(np.argsort(eb))
    consistent = bool(np.array_equal(a_rank, b_rank))
    return {
        "consistent": consistent,
        "energy_corr": float(np.corrcoef(ea, eb)[0, 1]) if ea.size > 1 and eb.size > 1 else 1.0,
        "max_energy_diff": float(np.max(np.abs(ea - eb))),
    }


def npu_boundary_report(*, torch_logits_arr: np.ndarray | None = None,
                        ort_logits_arr: np.ndarray | None = None,
                        fake_int8_arr: np.ndarray | None = None,
                        real_npu_logits: np.ndarray | None = None,
                        atol: float = 1e-3, rtol: float = 1e-3,
                        temperature: float = 1.0) -> dict[str, Any]:
    """Five-way consistency report; real-NPU absence is flagged, never fabricated."""
    present: dict[str, np.ndarray] = {}
    if torch_logits_arr is not None:
        present["torch"] = np.asarray(torch_logits_arr, dtype=np.float64)
    if ort_logits_arr is not None:
        present["ort"] = np.asarray(ort_logits_arr, dtype=np.float64)
    if fake_int8_arr is not None:
        present["fake_int8"] = np.asarray(fake_int8_arr, dtype=np.float64)

    comparisons: dict[str, Any] = {}
    mismatches: list[str] = []
    keys = list(present.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            k = f"{keys[i]}_vs_{keys[j]}"
            comparisons[k] = compare_logits(present[keys[i]], present[keys[j]],
                                            atol=atol, rtol=rtol)
            if not comparisons[k]["match"]:
                mismatches.append(k)

    npu_missing = real_npu_logits is None
    npu_note: str | None = None
    if npu_missing:
        npu_note = NPU_LOGITS_MISSING
    else:
        npu = np.asarray(real_npu_logits, dtype=np.float64)
        for name, arr in present.items():
            c = compare_logits(arr, npu, atol=atol, rtol=rtol)
            comparisons[f"{name}_vs_npu"] = c
            if not c["match"]:
                mismatches.append(f"{name}_vs_npu")

    status = BOUNDARY_OK if not mismatches else BOUNDARY_MISMATCH
    return {
        "status": status,
        "npu_logits_missing": npu_missing,
        "npu_note": npu_note,
        "representations_present": keys + ([] if npu_missing else ["npu"]),
        "comparisons": comparisons,
        "mismatches": mismatches,
    }


__all__ = [
    "NPU_LOGITS_MISSING", "BOUNDARY_OK", "BOUNDARY_MISMATCH", "energy_np",
    "fake_int8_logits", "torch_logits", "ort_logits", "compare_logits",
    "energy_direction_consistent", "npu_boundary_report",
]
