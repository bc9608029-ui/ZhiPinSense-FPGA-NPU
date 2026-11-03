#!/usr/bin/env python3
"""ppm2png.py -- convert PPM (P6 binary, RGB888) to PNG using only the stdlib.

Usage: python ppm2png.py IN.ppm OUT.png   (or: python ppm2png.py DIR)
       With DIR, converts every *.ppm in DIR to a sibling *.png.

Pure stdlib (zlib + struct).  No Pillow / numpy needed.
"""
import os
import struct
import sys
import zlib


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def ppm_to_png(src: str, dst: str) -> None:
    with open(src, "rb") as f:
        data = f.read()
    # header
    assert data[:2] == b"P6", f"not a P6 PPM: {src}"
    i = 2
    tokens = []
    while len(tokens) < 3:
        # skip whitespace / comments
        while i < len(data) and data[i] in b" \t\r\n":
            i += 1
        if data[i:i + 1] == b"#":
            while i < len(data) and data[i] != 0x0A:
                i += 1
            continue
        j = i
        while j < len(data) and data[j] not in b" \t\r\n":
            j += 1
        tokens.append(data[i:j])
        i = j
    w = int(tokens[0]); h = int(tokens[1]); maxv = int(tokens[2])
    assert maxv == 255, f"unexpected maxval {maxv}"
    while data[i] in b" \t\r\n":
        i += 1
    raw = data[i:i + w * h * 3]
    assert len(raw) == w * h * 3, f"short pixel data {len(raw)}"

    # PNG: each row prefixed by filter byte 0
    stride = w * 3
    rows = b"".join(b"\x00" + raw[y * stride:(y + 1) * stride] for y in range(h))
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(rows, 9))
    png += _chunk(b"IEND", b"")
    with open(dst, "wb") as f:
        f.write(png)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    if os.path.isdir(path):
        n = 0
        for name in sorted(os.listdir(path)):
            if name.endswith(".ppm"):
                src = os.path.join(path, name)
                dst = os.path.join(path, name[:-4] + ".png")
                ppm_to_png(src, dst)
                n += 1
        print(f"ppm2png: converted {n} files in {path}")
        return 0
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(path)[0] + ".png"
    ppm_to_png(path, dst)
    print(f"ppm2png: {path} -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
