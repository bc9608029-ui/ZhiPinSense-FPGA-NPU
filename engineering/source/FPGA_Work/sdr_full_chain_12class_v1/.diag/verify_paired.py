#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""要求 5「成对结果」：对同一批输入，并排输出
   (a) 预编译 ONNX 黄金 logits/argmax（expected_logits_or_argmax.json）
   (b) 编译产物 fake_qf 前向（fp32 反量化，Host）
   (c) 编译产物 真实 int8 语义前向（Host，无反量化近似）
   逐条 argmax 对齐，给出每条最大 logit 与 margin，便于定位 64QAM->16QAM 那类
   边界翻转是「量化所致」还是「编译链路 bug」。

样本集：每类取 2 条（共 24 条，覆盖 12 类）+ 3 条已知 mismatch（94/106/166）。
"""
import json, subprocess, os, struct, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICRAFT_RUN = r"C:/Icraft/CLI v3.39.0/bin/icraft-run.exe"
JSON = os.path.join(ROOT, "model_12class", "model_12class.json")
RAW = os.path.join(ROOT, "model_12class", "model_12class.raw")
GOLDEN_DIR = os.path.join(ROOT, "deployment_golden")
GOLDEN_JSON = os.path.join(GOLDEN_DIR, "expected_logits_or_argmax.json")
LOG_FQ = os.path.join(ROOT, ".icraft_paired_fq")
LOG_INT8 = os.path.join(ROOT, ".icraft_paired_int8")
CLS = ["OOK","4ASK","AM-DSB","WBFM","2FSK","GFSK","BPSK","QPSK","8PSK","16QAM","64QAM","OFDM"]

def read_ftmp(logpath):
    ft = os.path.join(logpath, "model_12class", "ftmpSFT", "922.ftmp")
    with open(ft) as f:
        return [float(x) for x in f.read().split()]

def run(idx, fake_qf, logpath):
    inp = os.path.join(GOLDEN_DIR, "input_%03d.bin" % idx)
    cmd = [ICRAFT_RUN, "--json", JSON, "--raw", RAW, "--input", inp,
           "--backends", "Host", "--dump_format", "SFT", "--dump_ftmp", "922",
           "--log_path", logpath]
    if fake_qf:
        cmd.append("--fake_qf")
    with open(os.devnull, "w") as devnull:
        subprocess.run(cmd, stdout=devnull, stderr=devnull, check=False)
    try:
        return read_ftmp(logpath)
    except Exception as e:
        return None

def main():
    # 每类取 2 条。黄金集是 12 类 round-robin：label = idx % 12，每类 20 条
    # （idx = label + 12*round, round=0..19）。取 round 0 与 round 1 两条。
    pick = []
    for label in range(12):
        pick += [label + 0 * 12, label + 1 * 12]
    for m in (94, 106, 166):
        if m not in pick:
            pick.append(m)
    pick = sorted(set(pick))

    g = json.load(open(GOLDEN_JSON))
    samples = {s["index"]: s for s in g["samples"]}

    matched_fq = matched_int8 = 0
    rows = []
    for idx in pick:
        ref = samples[idx]["argmax_idx"]
        onnx = samples[idx]["logits"]
        fq = run(idx, True, LOG_FQ)
        i8 = run(idx, False, LOG_INT8)
        pfq = max(range(12), key=lambda k: fq[k]) if fq and len(fq) == 12 else -1
        pi8 = max(range(12), key=lambda k: i8[k]) if i8 and len(i8) == 12 else -1
        matched_fq += (pfq == ref)
        matched_int8 += (pi8 == ref)
        # margin = logits[argmax] - max(other)
        def margin(v):
            a = max(range(12), key=lambda k: v[k])
            other = max(v[k] for k in range(12) if k != a)
            return v[a] - other
        rows.append((idx, ref, pfq, pi8,
                     margin(onnx), margin(fq) if fq and len(fq) == 12 else float("nan"),
                     margin(i8) if i8 and len(i8) == 12 else float("nan")))

    print("paired=idx ref|onnx_logits[ref]|fake_qf_argmax|real_int8_argmax|onnx_margin|fake_qf_margin|real_int8_margin")
    for (idx, ref, pfq, pi8, mo, mf, mi) in rows:
        onnx_ref = samples[idx]["logits"][ref]
        flag = "" if pfq == ref == pi8 else "  <-- DIFF"
        print("%03d %2d(%s) onnx[ref]=%.4f | fq_argmax=%2d(%s) i8_argmax=%2d(%s) | margin onnx=%.4f fq=%.4f i8=%.4f%s" %
              (idx, ref, CLS[ref], onnx_ref,
               pfq, CLS[pfq] if 0 <= pfq < 12 else "?", pi8, CLS[pi8] if 0 <= pi8 < 12 else "?",
               mo, mf, mi, flag))

    n = len(rows)
    print("\n=== PAIRED SUMMARY ===")
    print("n=%d fake_qf_matched=%d/%d (%.4f) real_int8_matched=%d/%d (%.4f)" %
          (n, matched_fq, n, matched_fq / n, matched_int8, n, matched_int8 / n))

if __name__ == "__main__":
    main()
