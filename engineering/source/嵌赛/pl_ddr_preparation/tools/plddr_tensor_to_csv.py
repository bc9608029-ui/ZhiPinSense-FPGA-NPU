#!/usr/bin/env python3
"""Convert channel-major PL-DDR Tensor bytes to board-capture CSV."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


FRAME_LENGTH = 1024
PLANES = 5
FRAME_BYTES = FRAME_LENGTH * PLANES
COLUMNS = [
    "frame_id",
    "sample_index",
    "buffer_id",
    "iq_i_int8",
    "iq_q_int8",
    "power_int8",
    "lag_re_int8",
    "lag_im_int8",
    "iq_i_addr",
    "iq_q_addr",
    "power_addr",
    "lag_re_addr",
    "lag_im_addr",
    "frame_start",
    "frame_done",
    "frame_error",
    "irq",
]


def signed_byte(value: int) -> int:
    return value if value < 128 else value - 256


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_bin", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--frames", type=int, default=19)
    args = parser.parse_args()

    payload = args.input_bin.read_bytes()
    expected_size = args.frames * FRAME_BYTES
    if len(payload) != expected_size:
        raise SystemExit(f"expected {expected_size} bytes, found {len(payload)}")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for frame_id in range(args.frames):
            frame_base = frame_id * FRAME_BYTES
            planes = [
                payload[frame_base + plane * FRAME_LENGTH : frame_base + (plane + 1) * FRAME_LENGTH]
                for plane in range(PLANES)
            ]
            for sample_index in range(FRAME_LENGTH):
                writer.writerow(
                    {
                        "frame_id": frame_id,
                        "sample_index": sample_index,
                        "buffer_id": frame_id & 1,
                        "iq_i_int8": signed_byte(planes[0][sample_index]),
                        "iq_q_int8": signed_byte(planes[1][sample_index]),
                        "power_int8": signed_byte(planes[2][sample_index]),
                        "lag_re_int8": signed_byte(planes[3][sample_index]),
                        "lag_im_int8": signed_byte(planes[4][sample_index]),
                        "iq_i_addr": sample_index,
                        "iq_q_addr": FRAME_LENGTH + sample_index,
                        "power_addr": sample_index,
                        "lag_re_addr": FRAME_LENGTH + sample_index,
                        "lag_im_addr": 2 * FRAME_LENGTH + sample_index,
                        "frame_start": int(sample_index == 0),
                        "frame_done": int(sample_index == FRAME_LENGTH - 1),
                        "frame_error": 0,
                        "irq": int(sample_index == FRAME_LENGTH - 1),
                    }
                )
    print(f"PLDDR_TENSOR_CSV_PASS frames={args.frames} rows={args.frames*FRAME_LENGTH}")


if __name__ == "__main__":
    main()
