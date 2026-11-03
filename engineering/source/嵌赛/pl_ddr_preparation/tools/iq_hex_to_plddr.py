#!/usr/bin/env python3
"""Convert frozen {Q[15:0],I[15:0]} hex words to PL-DDR bytes.

Each 32-bit word is stored little-endian so the first sample appears in
User_Ddr_rdata[31:0], matching the RTL lane convention.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import struct


EXPECTED_SAMPLES = 19 * 1024


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_hex", type=Path)
    parser.add_argument("output_bin", type=Path)
    parser.add_argument("--samples", type=int, default=EXPECTED_SAMPLES)
    args = parser.parse_args()

    words: list[int] = []
    for line_number, raw in enumerate(args.input_hex.read_text(encoding="ascii").splitlines(), 1):
        text = raw.strip()
        if not text:
            continue
        try:
            value = int(text, 16)
        except ValueError as exc:
            raise SystemExit(f"invalid hex at line {line_number}: {text!r}") from exc
        if not 0 <= value <= 0xFFFF_FFFF:
            raise SystemExit(f"word out of range at line {line_number}: {text}")
        words.append(value)

    if len(words) != args.samples:
        raise SystemExit(f"expected {args.samples} IQ words, found {len(words)}")

    payload = b"".join(struct.pack("<I", word) for word in words)
    if len(payload) % 64:
        raise SystemExit("IQ payload is not 64-byte aligned")
    args.output_bin.parent.mkdir(parents=True, exist_ok=True)
    args.output_bin.write_bytes(payload)
    print(f"IQ_PLDDR_BIN_PASS samples={len(words)} bytes={len(payload)} beats={len(payload)//64}")


if __name__ == "__main__":
    main()
