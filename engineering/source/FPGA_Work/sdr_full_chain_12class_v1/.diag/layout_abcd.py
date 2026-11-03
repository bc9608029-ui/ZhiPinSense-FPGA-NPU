#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""输入布局诊断（要求 3）：对 input_000.bin 构造 4 种布局，各自喂编译产物做
icraft-run（真实 int8 语义，无 --fake_qf）forward，输出 12 logits + argmax，
判断 iCraft 编译布局是否与 ONNX 契约相反。

  A = 正式 planar  [I0..I1023, Q0..Q1023]
  B = 交织        [I0,Q0,I1,Q1,...,I1023,Q1023]
  C = I/Q 交换    [Q0..Q1023, I0..I1023]
  D = Q 取反      [I0..I1023, -Q0..-Q1023]

golden sample[0]: argmax_idx=0 (OOK), logits[0]=14.726858139。
"""
import json, subprocess, os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICRAFT_RUN = r"C:/Icraft/CLI v3.39.0/bin/icraft-run.exe"
JSON = os.path.join(ROOT, "model_12class", "model_12class.json")
RAW = os.path.join(ROOT, "model_12class", "model_12class.raw")
INP = os.path.join(ROOT, "deployment_golden", "input_000.bin")
OUT = os.path.join(ROOT, ".diag", "layout_bins")
LOG = os.path.join(ROOT, ".icraft_layout")

def load_planar():
    with open(INP, "rb") as f:
        b = f.read()
    fl = list(struct.unpack("<2048f", b))
    I = fl[0:1024]
    Q = fl[1024:2048]
    return I, Q

def save(name, arr):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name)
    with open(p, "wb") as f:
        f.write(struct.pack("<%df" % len(arr), *arr))
    return p

def run(binpath):
    cmd = [ICRAFT_RUN, "--json", JSON, "--raw", RAW, "--input", binpath,
           "--backends", "Host", "--dump_format", "SFT", "--dump_ftmp", "922",
           "--log_path", LOG]
    with open(os.devnull, "w") as devnull:
        subprocess.run(cmd, stdout=devnull, stderr=devnull)
    ft = os.path.join(LOG, "model_12class", "ftmpSFT", "922.ftmp")
    with open(ft) as f:
        vals = [float(x) for x in f.read().split()]
    return vals

def main():
    I, Q = load_planar()
    A = I + Q                       # planar
    B = [v for pair in zip(I, Q) for v in pair]   # interleaved
    C = Q + I                       # I/Q swapped
    D = I + [-q for q in Q]         # Q negated

    g = json.load(open(os.path.join(ROOT, "deployment_golden", "expected_logits_or_argmax.json")))
    ref = g["samples"][0]
    print("golden sample[0]: argmax_idx=%d (%s) logits[0]=%.6f" %
          (ref["argmax_idx"], ref["argmax_class"], ref["logits"][0]))

    for tag, arr in [("A_planar", A), ("B_interleaved", B), ("C_iqswap", C), ("D_qneg", D)]:
        p = save(tag + ".bin", arr)
        vals = run(p)
        pred = max(range(12), key=lambda k: vals[k])
        cls = ["OOK","4ASK","AM-DSB","WBFM","2FSK","GFSK","BPSK","QPSK","8PSK","16QAM","64QAM","OFDM"]
        print("\n[%s] argmax=%d (%s)" % (tag, pred, cls[pred]))
        print("  logits = [" + ", ".join("%.4f" % v for v in vals) + "]")

if __name__ == "__main__":
    main()
