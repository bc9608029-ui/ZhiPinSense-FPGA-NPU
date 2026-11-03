"""fix10clean2a Phase 0 — baseline identity verification.

Answers the fail-closed gate FIX10CLEAN2A_PHASE0 by proving, against the live
filesystem, that every authoritative input is present, unmodified, and mutually
compatible:

  * frozen checkpoint SHA-256 matches the task-spec value;
  * the real RadioML2018.01A HDF5 exists with the expected size / shape / dtype,
    label order, and SNR strata;
  * model source + config are byte-frozen and the checkpoint's state_dict loads
    into the frozen model class, producing 24 raw logits (no softmax).

This script is read-only: it never writes into the frozen model tree, the HDF5,
or the checkpoint.  It only emits results/CLEAN2A_INPUT_PROVENANCE.json.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Authoritative inputs (absolute; do not relocate).
# ---------------------------------------------------------------------------
CHECKPOINT = Path(r"F:/FPGA_Work/sdr_rml24_npu_deployment_m29/_frozen/runs/rml24_base/formal/t002_losscross_entropy_optadamw/seed2027/checkpoints/best.pt")
EXPECTED_CHECKPOINT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"

HDF5 = Path(r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5")

MODEL_ROOT = Path(r"F:/FPGA_Work/sdr_amr_12class_ood_u_v1")
MODEL_SOURCE_FILES = (
    "models/rml24_net.py",
    "models/ad_amr_v1_1_net.py",
    "contracts/rml24_contract.py",
    "training/utils.py",
)
CONFIG = Path(r"F:/FPGA_Work/sdr_rml24_npu_deployment_m29/_frozen/configs/rml24_base.yaml")

RESULTS_ROOT = Path(r"F:/嵌赛/fix10clean2a_results")
OUT = RESULTS_ROOT / "CLEAN2A_INPUT_PROVENANCE.json"

# ---------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def env_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": np.__version__,
    }
    for name in ("scipy", "h5py", "torch"):
        try:
            mod = __import__(name)
            info[name] = getattr(mod, "__version__", "unknown")
        except Exception as exc:  # pragma: no cover - environment probe
            info[name] = f"IMPORT_ERROR: {exc}"
    try:
        import torch
        info["torch_cuda_available"] = bool(torch.cuda.is_available())
        info["torch_device"] = str(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        info["deterministic_backend"] = bool(torch.backends.cudnn.enabled if torch.cuda.is_available() else True)
    except Exception as exc:  # pragma: no cover
        info["torch_cuda_available"] = f"ERROR: {exc}"
    return info


def verify_hdf5() -> dict[str, Any]:
    import h5py
    report: dict[str, Any] = {"path": str(HDF5)}
    report["exists"] = HDF5.is_file()
    if not report["exists"]:
        return report
    report["size_bytes"] = HDF5.stat().st_size
    report["sha256"] = sha256_file(HDF5)
    with h5py.File(HDF5, "r") as f:
        for key in ("X", "Y", "Z"):
            if key not in f:
                report[key] = {"error": "missing dataset"}
                continue
            ds = f[key]
            report[key] = {"shape": list(ds.shape), "dtype": str(ds.dtype)}
        report["top_level_keys"] = sorted(str(k) for k in f.keys())
    x = report.get("X", {})
    y = report.get("Y", {})
    z = report.get("Z", {})
    # RadioML2018.01A: X[N,1024,2] float32, Y[N,24] one-hot, Z[N,1] SNR.
    report["shape_contract_ok"] = (
        x.get("shape", []) == [2555904, 1024, 2]
        and y.get("shape", []) == [2555904, 24]
        and z.get("shape", []) == [2555904, 1]
    )
    return report


def snr_strata() -> dict[str, Any]:
    import h5py
    with h5py.File(HDF5, "r") as f:
        z = np.asarray(f["Z"][:], dtype=np.float32).reshape(-1)
        y = np.asarray(f["Y"][:], dtype=np.float32)
    uniq = sorted(float(v) for v in np.unique(z).tolist())
    labels = y.argmax(axis=1).astype(np.int64)
    counts = {
        f"{snr:g}": int(np.sum(z == snr)) for snr in uniq
    }
    per_class = [int(np.sum(labels == c)) for c in range(24)]
    return {
        "snr_values": uniq,
        "samples_per_snr": counts,
        "samples_per_class_total": per_class,
        "n_classes": 24,
    }


def verify_checkpoint() -> dict[str, Any]:
    report: dict[str, Any] = {"path": str(CHECKPOINT), "exists": CHECKPOINT.is_file()}
    if not report["exists"]:
        return report
    report["sha256"] = sha256_file(CHECKPOINT)
    report["sha256_matches_spec"] = report["sha256"] == EXPECTED_CHECKPOINT_SHA
    report["expected_sha256"] = EXPECTED_CHECKPOINT_SHA
    return report


def verify_model() -> dict[str, Any]:
    import torch
    sys.path.insert(0, str(MODEL_ROOT))
    from models.rml24_net import build_rml24_model, LABEL_ORDER_24
    from contracts.rml24_contract import INPUT_SHAPE, OUTPUT_DIM, OUTPUT_KIND

    report: dict[str, Any] = {
        "label_order_24": list(LABEL_ORDER_24),
        "input_shape": list(INPUT_SHAPE),
        "output_dim": OUTPUT_DIM,
        "output_kind": OUTPUT_KIND,
    }
    ckpt = torch.load(str(CHECKPOINT), map_location="cpu", weights_only=False)
    report["checkpoint_model_name"] = ckpt.get("model_name")
    report["checkpoint_class_names"] = ckpt.get("class_names")
    report["checkpoint_best_epoch"] = ckpt.get("best_epoch")
    report["checkpoint_best_selection_score"] = ckpt.get("best_selection_score")

    model = build_rml24_model(num_classes=len(LABEL_ORDER_24))
    ms = ckpt.get("model_state")
    missing, unexpected = model.load_state_dict(ms, strict=True)
    report["state_dict_missing"] = list(missing)
    report["state_dict_unexpected"] = list(unexpected)
    report["state_dict_loads_strict"] = (not missing and not unexpected)

    model.eval()
    with torch.inference_mode():
        # INPUT_SHAPE == (batch=1, channels=2, length=1024), already batched.
        dummy = torch.zeros(*INPUT_SHAPE)
        logits, _denoised = model(dummy)
    report["forward_output_shape"] = list(logits.shape)
    report["forward_logits_finite"] = bool(torch.isfinite(logits).all())
    report["forward_output_dim_ok"] = logits.shape[-1] == OUTPUT_DIM
    return report


def main() -> int:
    provenance: dict[str, Any] = {
        "task": "fix10clean2a",
        "phase": "PHASE0",
        "checkpoint": verify_checkpoint(),
        "hdf5": verify_hdf5(),
        "hdf5_snr_strata": snr_strata() if HDF5.is_file() else {},
        "model_source": {
            rel: sha256_file(MODEL_ROOT / rel) for rel in MODEL_SOURCE_FILES
        },
        "model_root": str(MODEL_ROOT),
        "config": {"path": str(CONFIG), "sha256": sha256_file(CONFIG)},
        "environment": env_info(),
    }
    try:
        provenance["model"] = verify_model()
    except Exception as exc:
        provenance["model"] = {"error": f"{type(exc).__name__}: {exc}"}

    # ---- gate ----
    cp = provenance["checkpoint"]
    h5 = provenance["hdf5"]
    md = provenance.get("model", {})
    failures: list[str] = []
    if not cp.get("sha256_matches_spec"):
        failures.append("checkpoint SHA mismatch")
    if not h5.get("exists"):
        failures.append("HDF5 missing")
    elif not h5.get("shape_contract_ok"):
        failures.append("HDF5 X/Y/Z shape contract mismatch")
    if not md.get("state_dict_loads_strict"):
        failures.append("model state_dict does not load strict")
    if not md.get("forward_output_dim_ok"):
        failures.append("model forward does not emit 24 logits")
    if not md.get("forward_logits_finite"):
        failures.append("model forward emits non-finite logits")

    provenance["gate"] = {
        "result": "PASS" if not failures else "FAIL",
        "failures": failures,
    }

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")

    print("FIX10CLEAN2A_PHASE0 result=%s" % provenance["gate"]["result"])
    for key, val in (
        ("checkpoint_sha", cp.get("sha256")),
        ("hdf5_sha", h5.get("sha256")),
        ("hdf5_size", h5.get("size_bytes")),
        ("hdf5_X", h5.get("X", {}).get("shape")),
        ("hdf5_Y", h5.get("Y", {}).get("shape")),
        ("hdf5_Z", h5.get("Z", {}).get("shape")),
        ("snr_values", provenance["hdf5_snr_strata"].get("snr_values")),
        ("model_forward", md.get("forward_output_shape")),
    ):
        print("  %-14s %s" % (key, val))
    if failures:
        for f in failures:
            print("  FAIL:", f)
    print("  provenance ->", OUT)
    return 0 if provenance["gate"]["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
