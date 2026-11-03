#!/usr/bin/env python3
"""Pack frozen expected_core.csv into the proposed five-plane DDR layout.

This is a preparation-time verifier, not a replacement for hardware output.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


FRAME_LENGTH = 1024
FIELDS = ["iq_i_int8", "iq_q_int8", "power_int8", "lag_re_int8", "lag_im_int8"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("expected_csv", type=Path)
    parser.add_argument("output_bin", type=Path)
    parser.add_argument("--frames", type=int, default=19)
    args = parser.parse_args()

    with args.expected_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected_rows = args.frames * FRAME_LENGTH
    if len(rows) != expected_rows:
        raise SystemExit(f"expected {expected_rows} rows, found {len(rows)}")

    payload = bytearray(args.frames * len(FIELDS) * FRAME_LENGTH)
    for row_number, row in enumerate(rows):
        frame_id = row_number // FRAME_LENGTH
        sample_index = row_number % FRAME_LENGTH
        if int(row["frame_id"]) != frame_id or int(row["sample_index"]) != sample_index:
            raise SystemExit(f"ordering error at row {row_number}")
        frame_base = frame_id * len(FIELDS) * FRAME_LENGTH
        for plane, field in enumerate(FIELDS):
            value = int(row[field])
            if not -128 <= value <= 127:
                raise SystemExit(f"INT8 range error row={row_number} field={field} value={value}")
            payload[frame_base + plane * FRAME_LENGTH + sample_index] = value & 0xFF

    if len(payload) % 64:
        raise SystemExit("Tensor payload is not 64-byte aligned")
    args.output_bin.parent.mkdir(parents=True, exist_ok=True)
    args.output_bin.write_bytes(payload)
    print(
        f"EXPECTED_TO_PLDDR_PASS frames={args.frames} bytes={len(payload)} "
        f"beats={len(payload)//64}"
    )


if __name__ == "__main__":
    main()
