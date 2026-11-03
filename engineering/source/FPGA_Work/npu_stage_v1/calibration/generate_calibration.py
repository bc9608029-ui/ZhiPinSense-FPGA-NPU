#!/usr/bin/env python3
"""Generate FP32 calibration data for the iCraft 3.39 ZG330 quantizer.

Domain contract (this is the crux, do not change it silently):
  The NPU partition ONNX (time_power_phase_npu_partition_opset17.onnx) has two
  FP32 inputs: iq [1,2,1024] and physical_features [1,3,1024].  The FPGA
  Mandatory Core emits a five-plane SInt8 tensor (I,Q,power,lag1_re,lag1_im)
  and the NPU-only adapter dequantizes it with the frozen reference contract:

      iq_float          = iq_int8        * (1/127)     # range ~[-1, 1]
      physical_float    = physical_int8  * (2/127)     # range ~[-2, 2]

  Therefore the FP32 distribution the NPU actually sees at run time is the
  *dequantized FPGA domain*, NOT the raw training float.  Calibration data must
  be generated in that exact domain so the iCraft input scale matches run time.

  To reproduce that domain faithfully we reuse the frozen FPGA golden path:
      frozen synthetic/validation IQ (RMS 1.0) -> int16 (peak 30000)
      -> hardware.fpga.python.rtl_reference.mandatory_frame_reference (SInt8)
      -> dequantize (1/127, 2/127).

  Nothing here touches final_blind_test (the "test" split with seed 26090831 is
  never constructed).  We sample the frozen "train"/"val" distribution only.

Outputs (per sample index N):
  cal_data/iq_N.bin           : FP32 [1,2,1024]   NCL contiguous (I plane, Q plane)
  cal_data/physical_N.bin     : FP32 [1,3,1024]   NCL contiguous (power, lag_re, lag_im)
  forward_list.txt            : "iq_N.bin;physical_N.bin" per line (multi-input)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path("F:/嵌赛/rf_cognitive_system").resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from channel.awgn import add_awgn  # noqa: E402
from datasets.modulation_generator import generate_iq  # noqa: E402
from hardware.fpga.python.rtl_reference import mandatory_frame_reference  # noqa: E402
from hardware.fpga.vectors.generate_vectors import _int16_from_complex  # noqa: E402
from training.utils import load_config  # noqa: E402

IQ_SCALE = 1.0 / 127.0
PHYSICAL_SCALE = 2.0 / 127.0
FRAME_LENGTH = 1024


def dequantize_frame(iq_int16: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Run the frozen FPGA golden path and dequantize to FP32 NPU inputs."""
    ref = mandatory_frame_reference(iq_int16)
    iq_float = np.stack(
        (ref["iq_i_int8"].astype(np.float32), ref["iq_q_int8"].astype(np.float32)), axis=0
    ) * IQ_SCALE
    physical_float = np.stack(
        (
            ref["power_int8"].astype(np.float32),
            ref["lag_re_int8"].astype(np.float32),
            ref["lag_im_int8"].astype(np.float32),
        ),
        axis=0,
    ) * PHYSICAL_SCALE
    return iq_float.astype(np.float32), physical_float.astype(np.float32)


def generate(signal_config: dict, snr_values: list[float], num_samples: int, output_dir: Path, seed: int) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    modulations = [name.upper() for name in signal_config["modulations"]]
    rng = np.random.default_rng(seed)
    forward_lines: list[str] = []
    manifest_rows: list[dict] = []

    for index in range(num_samples):
        label = index % len(modulations)
        assigned_snr = snr_values[index % len(snr_values)]
        modulation = modulations[label]

        clean, _ = generate_iq(modulation, signal_config, rng)
        noisy, _ = add_awgn(clean, assigned_snr, rng)
        iq_int16 = _int16_from_complex(noisy)
        iq_float, physical_float = dequantize_frame(iq_int16)

        assert iq_float.shape == (2, FRAME_LENGTH)
        assert physical_float.shape == (3, FRAME_LENGTH)

        iq_path = output_dir / f"iq_{index}.bin"
        physical_path = output_dir / f"physical_{index}.bin"
        iq_float.tofile(iq_path)
        physical_float.tofile(physical_path)

        forward_lines.append(f"iq_{index}.bin;physical_{index}.bin")
        manifest_rows.append(
            {
                "index": index,
                "modulation": modulation,
                "label": label,
                "snr_db": assigned_snr,
                "iq_file": iq_path.name,
                "physical_file": physical_path.name,
            }
        )

    forward_list_path = output_dir.parent / "forward_list.txt"
    forward_list_path.write_text("\n".join(forward_lines) + "\n", encoding="utf-8")

    manifest = {
        "seed": seed,
        "num_samples": num_samples,
        "modulations": modulations,
        "snr_values": snr_values,
        "iq_scale": IQ_SCALE,
        "physical_scale": PHYSICAL_SCALE,
        "iq_shape": [1, 2, FRAME_LENGTH],
        "physical_shape": [1, 3, FRAME_LENGTH],
        "iq_bytes_per_sample": 2 * FRAME_LENGTH * 4,
        "physical_bytes_per_sample": 3 * FRAME_LENGTH * 4,
        "forward_list": str(forward_list_path),
        "rows": manifest_rows,
    }
    (output_dir.parent / "calibration_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/baseline.yaml")
    parser.add_argument("--snr-values", type=float, nargs="*", default=None)
    parser.add_argument("--num-samples", type=int, default=168)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "cal_data")
    args = parser.parse_args()

    config = load_config(args.config)
    signal_config = config["signal"]
    snr_values = args.snr_values if args.snr_values is not None else list(config["dataset"]["snr_values"])
    manifest = generate(signal_config, snr_values, args.num_samples, args.output_dir, args.seed)

    print(f"CALIBRATION_GENERATED samples={manifest['num_samples']}")
    print(f"  iq_scale={IQ_SCALE} physical_scale={PHYSICAL_SCALE}")
    print(f"  output_dir={args.output_dir}")
    print(f"  forward_list={manifest['forward_list']}")


if __name__ == "__main__":
    main()
