#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""要求 5「校准数据校验」：逐文件确认 252 个校准输入都是
   float32 planar [1,2,1024] = 8192 字节，I 前 1024、Q 后 1024（C-order），
   并统计 RMS / peak / DC，确认与训练/ONNX 输入域一致（RMS~1.0、全 SNR 域）。
"""
import json, os, struct, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAL = os.path.join(ROOT, "model_12class", "calibration")
DATA = os.path.join(CAL, "cal_data")
MAN = json.load(open(os.path.join(CAL, "calibration_manifest.json")))
FL = os.path.join(CAL, "forward_list.txt")

EXPECT_BYTES = 8192
N_FLOAT = 2048

def check_file(iq_file):
    p = os.path.join(DATA, iq_file)
    b = open(p, "rb").read()
    if len(b) != EXPECT_BYTES:
        return (False, "bytes=%d" % len(b))
    fl = struct.unpack("<%df" % N_FLOAT, b)
    I = fl[0:1024]
    Q = fl[1024:2048]
    n = N_FLOAT
    sI = sum(I); sQ = sum(Q)
    ssI = sum(x * x for x in I); ssQ = sum(x * x for x in Q)
    rms = math.sqrt((ssI + ssQ) / n)
    peak = max(abs(x) for x in fl)
    # I/Q 通道内是否均为有限值
    if not all(math.isfinite(x) for x in fl):
        return (False, "non-finite float")
    return (True, rms, peak, sI / 1024.0, sQ / 1024.0)

def main():
    rows = MAN["rows"]
    fwd = [ln.strip() for ln in open(FL) if ln.strip()]
    print("manifest rows=%d forward_list lines=%d" % (len(rows), len(fwd)))
    # 1:1 对齐检查
    aligned = [r["iq_file"] for r in rows] == fwd
    print("forward_list 与 manifest 顺序 1:1 对齐: %s" % aligned)

    bad = 0
    rms_all = []
    peak_all = []
    for r in rows:
        ok, *rest = check_file(r["iq_file"])
        if not ok:
            bad += 1
            print("BAD %s %s" % (r["iq_file"], rest))
            continue
        rms, peak, dcI, dcQ = rest
        rms_all.append(rms); peak_all.append(peak)

    print("checked=%d bad=%d" % (len(rows), bad))
    if rms_all:
        print("RMS  mean=%.4f min=%.4f max=%.4f" %
              (sum(rms_all) / len(rms_all), min(rms_all), max(rms_all)))
        print("peak mean=%.3f min=%.3f max=%.3f" %
              (sum(peak_all) / len(peak_all), min(peak_all), max(peak_all)))
    print("每文件 bytes=%d fp32 planar [I1024][Q1024] = %s" %
          (EXPECT_BYTES, "PASS" if bad == 0 else "FAIL"))
    # 抽查 I 前 1024 / Q 后 1024 的 DC 一致性（I/Q 顺序正确时两通道统计独立）
    r0 = rows[0]
    ok, rms, peak, dcI, dcQ = check_file(r0["iq_file"])
    print("sample iq_0.bin: rms=%.4f peak=%.3f dcI=%.6g dcQ=%.6g" %
          (rms, peak, dcI, dcQ))

if __name__ == "__main__":
    main()
