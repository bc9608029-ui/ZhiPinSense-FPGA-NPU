#!/usr/bin/env python3
# verify_stage_colors.py -- assert each captured screenshot's plot region is
# dominated by its expected stage color. Evidence (not a substitute for a human
# looking at the PNG): the stage scatter must be the most common non-background
# color inside the plot area (left 70%, below the title/legend band).
from PIL import Image

STAGE_COLORS = {
    "RAW_RX grey": (0xD0, 0xD4, 0xD8),
    "RECOVERED cyan": (0x22, 0xC3, 0xE6),
    "MODEL_INPUT green": (0x3D, 0xDC, 0x84),
    "SYMBOL_SAMPLED yellow": (0xE8, 0xC9, 0x3C),
    "outlier red": (0xE5, 0x60, 0x5F),
}
SHOTS = {
    "04_raw_rx.png": "RAW_RX grey",
    "02_recovered_payload_zh.png": "RECOVERED cyan",
    "03_model_input_zh.png": "MODEL_INPUT green",
    "07_symbol_sampled.png": "SYMBOL_SAMPLED yellow",
}


def close(c, t, tol=14):
    return all(abs(c[i] - t[i]) <= tol for i in range(3))


def main():
    ok = True
    for fname, expect_key in SHOTS.items():
        im = Image.open("screenshots/" + fname).convert("RGB")
        W, H = im.size
        px = im.load()
        counts = {k: 0 for k in STAGE_COLORS}
        for y in range(90, H):
            for x in range(0, 900):
                c = px[x, y]
                for k, t in STAGE_COLORS.items():
                    if close(c, t):
                        counts[k] += 1
                        break
        ranked = sorted(counts.items(), key=lambda kv: -kv[1])
        top = ranked[0]
        verdict = top[0] == expect_key
        ok = ok and verdict
        print("%-32s expect=%-20s top=%-20s (%5d px)  [%s]" %
              (fname, expect_key, top[0], top[1], "OK" if verdict else "MISMATCH"))
        print("    counts:", {k: v for k, v in ranked if v > 0})
    print("VERDICT:", "ALL-OK" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
