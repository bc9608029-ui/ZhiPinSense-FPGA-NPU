#!/usr/bin/env python3
"""PC reference inference for the frozen NPU partition (19-frame test vector).

This is the ground-truth the NPU-only board test will be compared against.  It
reproduces the exact runtime data path *without* onnxruntime and *without* the
iCraft toolchain:

    expected_tensor_plddr.bin (19 x 5-plane SInt8, 97,280 B)
      -> per-frame split into IQ [I,Q] and physical [power, lag_re, lag_im]
      -> dequantize with the FROZEN reference contract (iq x 1/127,
         physical x 2/127)  -- identical to the calibration domain
      -> TimePowerPhaseNPUPartition (best.pt, eval) -> 8 logits

Nothing here reads the "test" split or final_blind_test.  It only consumes the
already-frozen hardware capture image and the frozen checkpoint.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import torch

PROJECT_ROOT = Path("F:/嵌赛/rf_cognitive_system").resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from deployment.time_power_phase_partition import TimePowerPhaseNPUPartition, load_formal_candidate  # noqa: E402

FRAME_LENGTH = 1024
PLANES = 5
FRAME_BYTES = PLANES * FRAME_LENGTH  # 5120
NUM_FRAMES = 19
IQ_SCALE = 1.0 / 127.0
PHYSICAL_SCALE = 2.0 / 127.0

CLASS_ORDER = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]

# Ground truth for the frozen 19-frame vector (from expected_core.csv case_name).
GROUND_TRUTH = {
    0: None, 1: None, 2: None, 3: None, 4: None, 5: None, 6: None,   # OOD
    7: "BPSK", 8: "BPSK", 9: "BPSK",
    10: "QPSK", 11: "QPSK", 12: "QPSK",
    13: "16QAM", 14: "16QAM", 15: "16QAM",
    16: "64QAM", 17: "64QAM", 18: "64QAM",
}

CASE_NAMES = [
    "all_zero", "single_impulse", "positive_negative_alternating",
    "maximum_positive", "maximum_negative", "near_full_scale", "random_iq",
    "bpsk_snr_p20db", "bpsk_snr_p0db", "bpsk_snr_m10db",
    "qpsk_snr_p20db", "qpsk_snr_p0db", "qpsk_snr_m10db",
    "16qam_snr_p20db", "16qam_snr_p0db", "16qam_snr_m10db",
    "64qam_snr_p20db", "64qam_snr_p0db", "64qam_snr_m10db",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    exp = np.exp(shifted)
    return exp / np.sum(exp)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tensor", type=Path,
                        default=Path("F:/嵌赛/pl_ddr_preparation/generated/expected_tensor_plddr.bin"))
    parser.add_argument("--checkpoint", type=Path,
                        default=PROJECT_ROOT / "outputs/qam_aware_v2/formal/time_power_phase/checkpoints/best.pt")
    parser.add_argument("--config", default="configs/qam_aware_v2.yaml")
    parser.add_argument("--out-json", type=Path,
                        default=Path(__file__).resolve().parent / "pc_reference_19frames.json")
    parser.add_argument("--out-csv", type=Path,
                        default=Path(__file__).resolve().parent / "pc_reference_19frames.csv")
    args = parser.parse_args()

    torch.manual_seed(0)
    np.random.seed(0)

    model, checkpoint = load_formal_candidate(args.config, args.checkpoint)
    model.eval()
    partition = TimePowerPhaseNPUPartition(model)
    partition.eval()

    payload = args.tensor.read_bytes()
    assert len(payload) == NUM_FRAMES * FRAME_BYTES, (
        f"expected {NUM_FRAMES * FRAME_BYTES} B, got {len(payload)}"
    )
    tensor = np.frombuffer(payload, dtype=np.int8).reshape(NUM_FRAMES, PLANES, FRAME_LENGTH)

    rows = []
    with torch.inference_mode():
        for frame_id in range(NUM_FRAMES):
            iq_int8 = tensor[frame_id, 0:2, :].astype(np.float32)            # [2, 1024]
            physical_int8 = tensor[frame_id, 2:5, :].astype(np.float32)      # [3, 1024]

            iq_float = iq_int8 * IQ_SCALE
            physical_float = physical_int8 * PHYSICAL_SCALE

            iq_t = torch.from_numpy(iq_float[None, :, :])                    # [1, 2, 1024]
            physical_t = torch.from_numpy(physical_float[None, :, :])        # [1, 3, 1024]

            logits_t = partition(iq_t, physical_t)[0]                        # [8]
            logits = logits_t.detach().numpy().astype(np.float32)
            probs = softmax(logits)

            order = np.argsort(logits)[::-1]
            argmax = int(order[0])
            top1_conf = float(probs[argmax])
            top1_top2_margin = float(probs[order[0]] - probs[order[1]])

            gt = GROUND_TRUTH[frame_id]
            rows.append({
                "frame_id": frame_id,
                "case_name": CASE_NAMES[frame_id],
                "ood": gt is None,
                "ground_truth": gt if gt is not None else "OOD",
                "ground_truth_id": CLASS_ORDER.index(gt) if gt is not None else None,
                "logits": [float(x) for x in logits],
                "argmax_id": argmax,
                "argmax_class": CLASS_ORDER[argmax],
                "top1_confidence": top1_conf,
                "top1_top2_margin": top1_top2_margin,
                "correct": (gt is not None) and (argmax == CLASS_ORDER.index(gt)),
            })

    valid = [r for r in rows if not r["ood"]]
    accuracy = sum(1 for r in valid if r["correct"]) / len(valid) if valid else None

    report = {
        "schema": "pc_reference_npu_partition_v1",
        "checkpoint": {
            "path": str(args.checkpoint),
            "sha256": sha256(args.checkpoint),
            "epoch": checkpoint.get("epoch"),
            "best_epoch": checkpoint.get("best_epoch"),
        },
        "input_tensor": {
            "path": str(args.tensor),
            "sha256": sha256(args.tensor),
            "bytes": len(payload),
            "frames": NUM_FRAMES,
            "frame_bytes": FRAME_BYTES,
            "layout": ["iq_i_int8", "iq_q_int8", "power_int8", "lag_re_int8", "lag_im_int8"],
        },
        "dequant_contract": {
            "iq_scale": IQ_SCALE,
            "physical_scale": PHYSICAL_SCALE,
            "zero_point": 0,
            "symmetric": True,
        },
        "class_order": CLASS_ORDER,
        "valid_accuracy": accuracy,
        "valid_frames": len(valid),
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "numpy": np.__version__,
            "random_seed": 0,
            "torch_inference_mode": True,
            "model_eval": True,
            "command": " ".join(sys.argv),
        },
        "frames": rows,
    }

    args.out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    csv_fields = [
        "frame_id", "case_name", "ood", "ground_truth", "ground_truth_id",
        "argmax_id", "argmax_class", "top1_confidence", "top1_top2_margin",
        "correct",
    ] + [f"logit_{i}" for i in range(8)]
    with args.out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for r in rows:
            out = {k: r[k] for k in csv_fields[:10]}
            for i in range(8):
                out[f"logit_{i}"] = r["logits"][i]
            writer.writerow(out)

    print("PC_REFERENCE_COMPLETE")
    for r in rows:
        flag = "OOD " if r["ood"] else ("OK  " if r["correct"] else "MISS")
        print(f"  {flag} frame={r['frame_id']:2d} {r['case_name']:28s} "
              f"gt={r['ground_truth']:>5s} -> {r['argmax_class']:>6s} "
              f"conf={r['top1_confidence']:.4f} margin={r['top1_top2_margin']:.4f}")
    print(f"valid_accuracy={accuracy} ({sum(1 for r in valid if r['correct'])}/{len(valid)})")
    print(f"json={args.out_json}")
    print(f"csv={args.out_csv}")


if __name__ == "__main__":
    main()
