"""Fail-closed offline audit before transmitting the 24 clean generated waveforms."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from clean_v2_common import FIXED_SCALE, LABELS, build_frame, load_clean_samples, load_public_pilots, verify_receiver


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset-root", type=Path, default=Path(r"F:\嵌赛\fix10class24_waveform_correct_v2_work"))
    ap.add_argument("--rescue-root", type=Path, default=Path(r"F:\AMR_Rescue_20261025"))
    ap.add_argument("--out-json", type=Path)
    args = ap.parse_args()
    receiver = verify_receiver(args.rescue_root)
    train, tail = load_public_pilots(args.rescue_root)
    samples = load_clean_samples(args.asset_root)
    scales = []
    peaks = []
    for sample in samples:
        frame, scale = build_frame(sample, train, tail)
        scales.append(scale)
        peaks.append(float(max(abs(frame.real).max(), abs(frame.imag).max())))
    if [x.class_name for x in samples] != list(LABELS):
        raise RuntimeError("24-class order/coverage mismatch")
    if any(abs(s - FIXED_SCALE) > 1e-12 for s in scales):
        raise RuntimeError("per-sample peak cap activated; fixed-amplitude clean test is invalid")
    correct = sum(x.digital_correct for x in samples)
    errors = [{"source_index": x.source_index, "class_index": x.class_index,
               "class_name": x.class_name, "digital_pred": x.digital_pred}
              for x in samples if not x.digital_correct]
    if correct != 23 or errors != [{"source_index": 21, "class_index": 20,
                                     "class_name": "AM-DSB-SC", "digital_pred": 16}]:
        raise RuntimeError(f"unexpected frozen digital baseline: correct={correct}, errors={errors}")
    tx_text = (HERE / "pc_clean_v2_tx.py").read_text(encoding="utf-8")
    forbidden = ("source_manifest_960", "GOLD_XYZ", ".hdf5", "line_a/inputs")
    hit = [x for x in forbidden if x in tx_text]
    if hit:
        raise RuntimeError(f"transmitter references dataset assets: {hit}")
    report = {
        "result": "PASS",
        "test_kind": "generated_clean_v2_public_frame",
        "n_sources": len(samples),
        "class_coverage": "24/24",
        "digital_baseline_correct": "23/24",
        "known_digital_error": errors,
        "frame_complex": 16384,
        "payload_complex": 1024,
        "payload_repeats": 8,
        "fixed_scale": FIXED_SCALE,
        "scale_fixed_24_of_24": True,
        "max_unscaled_component": max(peaks),
        "receiver_sha256": receiver,
        "receiver_gets_only_sequence_number": True,
        "uses_original_dataset_iq": False,
    }
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
