#!/usr/bin/env python3
# ppm_to_png.py -- convert PPM (P6) screenshots to PNG (fix10class24-waterfall1).
# Usage: python3 ppm_to_png.py <file.ppm> [more.ppm ...]
# Writes <file>.png next to each input.
import os
import sys

from PIL import Image


def main(argv):
    if not argv:
        print("usage: ppm_to_png.py <file.ppm> [...]", file=sys.stderr)
        return 2
    rc = 0
    for ppm in argv:
        png = os.path.splitext(ppm)[0] + ".png"
        try:
            with Image.open(ppm) as im:
                im.convert("RGB").save(png, "PNG")
            print("wrote", png)
        except Exception as e:  # noqa: BLE001
            print("FAILED", ppm, "->", e, file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
