#!/usr/bin/env python3
"""Losslessly convert binary payloads to/from one-byte-per-line hex."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("encode", "decode"))
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    args.destination.parent.mkdir(parents=True, exist_ok=True)
    if args.mode == "encode":
        payload = args.source.read_bytes()
        args.destination.write_text(
            "".join(f"{value:02x}\n" for value in payload), encoding="ascii"
        )
    else:
        values = []
        for line_number, raw in enumerate(
            args.source.read_text(encoding="ascii").splitlines(), start=1
        ):
            token = raw.strip()
            if not token:
                continue
            if len(token) != 2:
                raise SystemExit(f"invalid byte at line {line_number}: {token!r}")
            values.append(int(token, 16))
        args.destination.write_bytes(bytes(values))
    print(
        f"BYTE_HEX_{args.mode.upper()}_PASS bytes={args.destination.stat().st_size if args.mode == 'decode' else len(payload)}"
    )


if __name__ == "__main__":
    main()
