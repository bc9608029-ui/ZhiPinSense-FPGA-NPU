#!/usr/bin/env python3
"""build_fix10class24_dualsdr_rf_dataset.py -- assemble the dual-SDR RF dataset.

Pure-stdlib, runs under ``python -I``.  Consumes a directory of real-RF
captures and emits the v1 dataset (manifest + leak-free splits + copied
model-input tensors) under ``datasets/rml24_dualsdr_rf_v1/``.

Input layout (one subdir per capture under ``--capture-root``)::

    <capture-root>/
      <sample_id>/
        capture_meta.json      # source_index, link, gate_status, capture_session_id, ...
        model_input.f32        # REQUIRED: 8192-byte [2,1024] fp32 LE (production chain)
        model_input_wl.f32     # optional: wide-linear variant (same shape)

``capture_meta.json`` required fields: source_index (int), link (single|dual),
gate_status (PASSED|DIAGNOSTIC_PROVISIONAL|REJECTED), capture_session_id (str).
Optional: payload_training_residual, corr, cfo_hz, wide_linear_ratio,
capture_attempts, raw_rx_iq_sha256.

Fail-closed rules (any violation aborts the build, nothing partial is written):

* ``source_index`` must be a planned slot (offset < 40) and globally unique.
* split role is derived from the offset via the frozen plan; a sample whose
  offset is outside the plan, or whose ``source_index`` is duplicated, aborts.
* train/val/test splits accept ONLY ``gate_status == PASSED``.
  ``DIAGNOSTIC_PROVISIONAL`` samples are retained into ``pilot`` only, never
  into train/val/test (they are kept for diagnosis, not for the main set).
  ``REJECTED`` samples are recorded and excluded.
* model_input.f32 must exist, be exactly 8192 bytes, and be a finite fp32 tensor.

Usage::

    python -I scripts/build_fix10class24_dualsdr_rf_dataset.py \
        --capture-root <dir> --out-dir datasets/rml24_dualsdr_rf_v1
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import struct
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "contracts"))
import rml24_dualsdr_rf_dataset_v1 as C  # noqa: E402

MODEL_INPUT_BYTES = C.MODEL_IO["input_bytes"]
SCALAR_FILENAME = "model_input.f32"
WL_FILENAME = "model_input_wl.f32"

REQUIRED_META = ("source_index", "link", "gate_status", "capture_session_id")
OPTIONAL_META = (
    "payload_training_residual", "corr", "cfo_hz", "wide_linear_ratio",
    "capture_attempts", "raw_rx_iq_sha256",
)


class BuildError(Exception):
    pass


def sha256_file(path) -> str:
    return C.sha256_file(path)


def _finite_fp32(path) -> None:
    """Verify a model_input file is exactly 8192 bytes of finite fp32 LE."""
    raw = Path(path).read_bytes()
    if len(raw) != MODEL_INPUT_BYTES:
        raise BuildError(f"{path}: {len(raw)} bytes (want {MODEL_INPUT_BYTES})")
    n = MODEL_INPUT_BYTES // 4
    vals = struct.unpack(f"<{n}f", raw)
    if not all(math.isfinite(v) for v in vals):
        raise BuildError(f"{path}: non-finite fp32 value")


def load_meta(meta_path) -> dict:
    try:
        meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise BuildError(f"bad capture_meta.json {meta_path}: {e}")
    if not isinstance(meta, dict):
        raise BuildError(f"{meta_path}: capture_meta.json must be a JSON object")
    for field in REQUIRED_META:
        if field not in meta:
            raise BuildError(f"{meta_path}: missing required field {field!r}")
    return meta


def build(capture_root, out_dir, allow_provisional: bool = False):
    """Assemble the dataset.  Returns a report dict; raises BuildError on violation."""
    capture_root = Path(capture_root)
    if not capture_root.is_dir():
        raise BuildError(f"capture root not a directory: {capture_root}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    splits_dir = out_dir / "splits"
    inputs_dir = out_dir / "model_inputs"
    splits_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir.mkdir(parents=True, exist_ok=True)

    planned = {r["source_index"]: r for r in C.capture_plan_rows()}

    rows = []
    rejected = []
    provisional = []
    seen_source_index = {}

    sample_dirs = sorted(
        [p for p in capture_root.iterdir() if p.is_dir()],
        key=lambda p: p.name,
    )
    if not sample_dirs:
        raise BuildError(f"no capture subdirs under {capture_root}")

    for sd in sample_dirs:
        sample_id = sd.name
        meta = load_meta(sd / "capture_meta.json")

        source_index = meta["source_index"]
        if not isinstance(source_index, int):
            raise BuildError(f"{sample_id}: source_index must be int")
        if source_index not in planned:
            raise BuildError(
                f"{sample_id}: source_index {source_index} is not a planned slot (offset>=40?)"
            )
        if source_index in seen_source_index:
            raise BuildError(
                f"{sample_id}: duplicate source_index {source_index} "
                f"(already seen in {seen_source_index[source_index]})"
            )
        seen_source_index[source_index] = sample_id

        plan = planned[source_index]
        phase = plan["phase"]
        offset = plan["intra_class_offset"]
        role = plan["split_role"]
        class_index = plan["raw24_class_index"]

        link = meta["link"]
        if link not in ("single", "dual"):
            raise BuildError(f"{sample_id}: link must be single|dual, got {link!r}")

        gate_status = meta["gate_status"]
        if gate_status not in C.GATE_STATUSES:
            raise BuildError(f"{sample_id}: bad gate_status {gate_status!r}")

        scalar_path = sd / SCALAR_FILENAME
        wl_path = sd / WL_FILENAME
        if not scalar_path.is_file():
            raise BuildError(f"{sample_id}: missing {SCALAR_FILENAME}")
        _finite_fp32(scalar_path)
        model_input_sha = sha256_file(scalar_path)
        has_wl = wl_path.is_file()

        if gate_status == C.GATE_REJECTED:
            rejected.append({"sample_id": sample_id, "source_index": source_index})
            continue
        if gate_status == C.GATE_DIAGNOSTIC_PROVISIONAL:
            # provisional samples may only be retained into pilot (never main set)
            provisional.append({"sample_id": sample_id, "source_index": source_index})
            if role in ("train", "val", "test"):
                raise BuildError(
                    f"{sample_id}: DIAGNOSTIC_PROVISIONAL sample has split_role "
                    f"{role!r}; provisional may only enter 'pilot'"
                )
            if not allow_provisional and role != "pilot":
                raise BuildError(
                    f"{sample_id}: provisional sample excluded (not pilot and "
                    f"--allow-provisional not set)"
                )
        if role in ("train", "val", "test") and gate_status != C.GATE_PASSED:
            raise BuildError(
                f"{sample_id}: {role} split requires PASSED, got {gate_status}"
            )

        label = plan["raw24_label"]
        row = {
            "sample_id": sample_id,
            "source_index": source_index,
            "raw24_class_index": class_index,
            "raw24_label": label,
            "deployed23_index": C.deployed23_index_of(class_index),
            "deployed23_label": C.deployed23_label_of(class_index),
            "modulation": label,
            "intra_class_offset": offset,
            "phase": phase,
            "split_role": role,
            "link": link,
            "gate_status": gate_status,
            "payload_training_residual": meta.get("payload_training_residual", ""),
            "corr": meta.get("corr", ""),
            "cfo_hz": meta.get("cfo_hz", ""),
            "wide_linear_ratio": meta.get("wide_linear_ratio", ""),
            "capture_attempts": meta.get("capture_attempts", ""),
            "capture_session_id": meta["capture_session_id"],
            "center_freq_hz": C.RF_CONFIG["center_freq_hz"],
            "sample_rate_hz": C.RF_CONFIG["sample_rate_hz"],
            "rx_gain": C.RF_CONFIG["rx_gain"],
            "rx_bw_hz": C.RF_CONFIG["rx_bw_hz"],
            "tx_bw_hz": C.RF_CONFIG["tx_bw_hz"],
            "tx_atten_db": C.RF_CONFIG["tx_atten_db"],
            "tx_target_rms": C.RF_CONFIG["tx_target_rms"],
            "rf_path": C.RF_CONFIG["rf_path"],
            "raw_rx_iq_sha256": meta.get("raw_rx_iq_sha256", ""),
            "model_input_sha256": model_input_sha,
            "frozen_raw24_pred": meta.get("frozen_raw24_pred", ""),
        }
        rows.append(row)

        # copy the scalar tensor into the canonical dataset location
        shutil.copyfile(scalar_path, inputs_dir / f"{sample_id}.f32")
        if has_wl:
            _finite_fp32(wl_path)
            shutil.copyfile(wl_path, inputs_dir / f"{sample_id}.wl.f32")

    if not rows:
        raise BuildError("no accepted samples (all rejected/provisional?)")

    # leak check: split roles are derived from the frozen plan, so they are
    # disjoint by construction; still assert no source_index appears twice.
    manifest_path = out_dir / "manifest.tsv"
    _write_tsv(manifest_path, C.MANIFEST_COLUMNS, rows)

    for role in ("train", "val", "test", "pilot"):
        subset = [r for r in rows if r["split_role"] == role]
        _write_tsv(splits_dir / f"{role}.tsv", C.MANIFEST_COLUMNS, subset)

    report = {
        "contract_sha256": C.dataset_contract_sha256(),
        "capture_root": str(capture_root),
        "out_dir": str(out_dir),
        "accepted": len(rows),
        "rejected": len(rejected),
        "provisional_retained": len([p for p in provisional if p["source_index"] in
                                     {r["source_index"] for r in rows}]),
        "rejected_samples": rejected,
        "split_counts": {role: sum(1 for r in rows if r["split_role"] == role)
                         for role in ("train", "val", "test", "pilot")},
        "per_class_accepted": _per_class(rows),
    }
    (out_dir / "build_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _per_class(rows) -> dict:
    out = {}
    for r in rows:
        out.setdefault(r["raw24_label"], 0)
        out[r["raw24_label"]] += 1
    return out


def _fmt(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return ""
    return str(v)


def _write_tsv(path, columns, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(columns) + "\n")
        for r in rows:
            f.write("\t".join(_fmt(r.get(c, "")) for c in columns) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture-root", required=True)
    ap.add_argument("--out-dir", default="datasets/rml24_dualsdr_rf_v1")
    ap.add_argument("--allow-provisional", action="store_true",
                    help="retain DIAGNOSTIC_PROVISIONAL samples into 'pilot' (never train/val/test)")
    args = ap.parse_args()
    try:
        report = build(args.capture_root, args.out_dir, args.allow_provisional)
    except BuildError as e:
        print(f"build FAILED: {e}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"dataset built -> {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
