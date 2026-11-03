"""Generate deterministic IQ and expected mandatory-path RTL vectors."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from channel.awgn import add_awgn
from datasets.modulation_generator import generate_iq
from hardware.fpga.python.rtl_reference import (
    REFERENCE_IQ_QUANTIZER,
    REFERENCE_PHYSICAL_QUANTIZER,
    mandatory_frame_reference,
)
from training.utils import load_config


FRAME_LENGTH = 1024
SEED = 20261001


def _int16_from_complex(values: np.ndarray, peak_count: int = 30_000) -> np.ndarray:
    peak = float(max(np.max(np.abs(values.real)), np.max(np.abs(values.imag))))
    if peak == 0.0:
        return np.zeros((len(values), 2), dtype=np.int16)
    scaled = values * (peak_count / peak)
    return np.stack((np.rint(scaled.real), np.rint(scaled.imag)), axis=1).astype(np.int16)


def build_cases() -> list[tuple[str, np.ndarray, dict[str, object]]]:
    rng = np.random.default_rng(SEED)
    cases: list[tuple[str, np.ndarray, dict[str, object]]] = []

    cases.append(("all_zero", np.zeros((FRAME_LENGTH, 2), dtype=np.int16), {}))
    impulse = np.zeros((FRAME_LENGTH, 2), dtype=np.int16)
    impulse[511] = (32767, -32768)
    cases.append(("single_impulse", impulse, {}))
    alternating = np.empty((FRAME_LENGTH, 2), dtype=np.int16)
    alternating[0::2] = (32767, -32768)
    alternating[1::2] = (-32768, 32767)
    cases.append(("positive_negative_alternating", alternating, {}))
    cases.append(("maximum_positive", np.full((FRAME_LENGTH, 2), 32767, dtype=np.int16), {}))
    cases.append(("maximum_negative", np.full((FRAME_LENGTH, 2), -32768, dtype=np.int16), {}))
    cases.append(
        (
            "near_full_scale",
            rng.integers(-32000, 32001, size=(FRAME_LENGTH, 2), dtype=np.int16),
            {},
        )
    )
    random_iq = np.clip(np.rint(rng.normal(0.0, 7000.0, size=(FRAME_LENGTH, 2))), -32768, 32767)
    cases.append(("random_iq", random_iq.astype(np.int16), {}))

    signal_config = load_config("configs/baseline.yaml")["signal"]
    for modulation in ("BPSK", "QPSK", "16QAM", "64QAM"):
        for snr_db in (20.0, 0.0, -10.0):
            clean, metadata = generate_iq(modulation, signal_config, rng)
            noisy, noise_meta = add_awgn(clean, snr_db, rng)
            case_name = f"{modulation.lower()}_snr_{snr_db:+.0f}db".replace("+", "p").replace("-", "m")
            cases.append(
                (
                    case_name,
                    _int16_from_complex(noisy),
                    {"modulation": modulation, "snr_db": snr_db, "generator": metadata, "awgn": noise_meta},
                )
            )
    return cases


def generate(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = build_cases()
    input_path = output_dir / "iq_input.hex"
    expected_path = output_dir / "expected_core.csv"
    manifest_path = output_dir / "manifest.json"
    header_path = output_dir / "vector_params.svh"

    records: list[dict[str, object]] = []
    with input_path.open("w", encoding="ascii", newline="\n") as input_file, expected_path.open(
        "w", encoding="utf-8", newline=""
    ) as expected_file:
        fieldnames = [
            "case_id", "case_name", "frame_id", "sample_index", "i", "q", "power", "lag_re", "lag_im",
            "iq_i_int8", "iq_q_int8", "power_int8", "lag_re_int8", "lag_im_int8",
            "iq_i_addr", "iq_q_addr", "power_addr", "lag_re_addr", "lag_im_addr",
        ]
        writer = csv.DictWriter(expected_file, fieldnames=fieldnames)
        writer.writeheader()
        for case_id, (name, iq, metadata) in enumerate(cases):
            reference = mandatory_frame_reference(iq, frame_id=case_id)
            records.append({"case_id": case_id, "name": name, "metadata": metadata})
            for index in range(FRAME_LENGTH):
                i_unsigned = int(iq[index, 0]) & 0xFFFF
                q_unsigned = int(iq[index, 1]) & 0xFFFF
                input_file.write(f"{q_unsigned:04x}{i_unsigned:04x}\n")
                writer.writerow(
                    {
                        "case_id": case_id,
                        "case_name": name,
                        "frame_id": case_id,
                        "sample_index": index,
                        "i": int(iq[index, 0]),
                        "q": int(iq[index, 1]),
                        "power": int(reference["power_u32_exact"][index]),
                        "lag_re": int(reference["lag1_real_s33_exact"][index]),
                        "lag_im": int(reference["lag1_imag_s33_exact"][index]),
                        "iq_i_int8": int(reference["iq_i_int8"][index]),
                        "iq_q_int8": int(reference["iq_q_int8"][index]),
                        "power_int8": int(reference["power_int8"][index]),
                        "lag_re_int8": int(reference["lag_re_int8"][index]),
                        "lag_im_int8": int(reference["lag_im_int8"][index]),
                        "iq_i_addr": int(reference["iq_i_addr"][index]),
                        "iq_q_addr": int(reference["iq_q_addr"][index]),
                        "power_addr": int(reference["power_addr"][index]),
                        "lag_re_addr": int(reference["lag_re_addr"][index]),
                        "lag_im_addr": int(reference["lag_im_addr"][index]),
                    }
                )

    manifest = {
        "schema_version": 1,
        "seed": SEED,
        "frame_length": FRAME_LENGTH,
        "case_count": len(cases),
        "total_samples": len(cases) * FRAME_LENGTH,
        "iq_word_layout": "hex {Q[15:0], I[15:0]}",
        "physical_channel_order": ["power", "lag_re", "lag_im"],
        "iq_quantizer": REFERENCE_IQ_QUANTIZER.as_dict(),
        "physical_quantizer": REFERENCE_PHYSICAL_QUANTIZER.as_dict(),
        "cases": records,
        "blind_test_accessed": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    header_path.write_text(
        "// Generated by vectors/generate_vectors.py\n"
        f"`define FPGA_VECTOR_FRAME_LENGTH {FRAME_LENGTH}\n"
        f"`define FPGA_VECTOR_CASE_COUNT {len(cases)}\n"
        f"`define FPGA_VECTOR_TOTAL_SAMPLES {len(cases) * FRAME_LENGTH}\n",
        encoding="ascii",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    manifest = generate(args.output)
    print(json.dumps({key: manifest[key] for key in ("seed", "case_count", "total_samples")}, indent=2))


if __name__ == "__main__":
    main()
