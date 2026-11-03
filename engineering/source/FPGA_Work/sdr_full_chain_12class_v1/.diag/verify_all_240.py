#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""离线验证：编译产物 model_12class.json/.raw 对 240 条 deployment_golden 输入
做 icraft-run Host --fake_qf forward，逐条 argmax 与 expected_logits_or_argmax.json 比对。

用法: python verify_all_240.py [N]
  缺省 N=240；N 用于快速冒烟（如 N=24 只跑前 24 条）。
"""
import json, subprocess, sys, os, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICRAFT_RUN = r"C:/Icraft/CLI v3.39.0/bin/icraft-run.exe"
JSON = os.path.join(ROOT, "model_12class", "model_12class.json")
RAW = os.path.join(ROOT, "model_12class", "model_12class.raw")
GOLDEN_DIR = os.path.join(ROOT, "deployment_golden")
LOG_PATH = os.path.join(ROOT, ".icraft_dump240")
GOLDEN_JSON = os.path.join(GOLDEN_DIR, "expected_logits_or_argmax.json")
FTMP = os.path.join(LOG_PATH, "model_12class", "ftmpSFT", "922.ftmp")

def read_output_ftmp():
    with open(FTMP, "r") as f:
        txt = f.read()
    vals = [float(x) for x in txt.split()]
    return vals

def run_one(idx):
    inp = os.path.join(GOLDEN_DIR, "input_%03d.bin" % idx)
    cmd = [ICRAFT_RUN, "--json", JSON, "--raw", RAW, "--input", inp,
           "--backends", "Host", "--fake_qf",
           "--dump_format", "SFT", "--dump_ftmp", "922",
           "--log_path", LOG_PATH]
    # 静默 icraft-run 的进度条/告警，只关心退出码与导出的 922.ftmp
    with open(os.devnull, "w") as devnull:
        subprocess.run(cmd, stdout=devnull, stderr=devnull, check=False)
    # 清理可能的旧文件后重新读取（icraft-run 会覆写同一 922.ftmp）
    try:
        logits = read_output_ftmp()
    except Exception as e:
        return None, str(e)
    if len(logits) != 12:
        return None, "len(logits)=%d" % len(logits)
    return logits, None

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 240
    g = json.load(open(GOLDEN_JSON))
    samples = g["samples"]
    n = min(n, len(samples))
    matched = 0
    mism = []
    t0 = time.time()
    for i in range(n):
        logits, err = run_one(i)
        ref = samples[i]["argmax_idx"]
        if err:
            mism.append((i, ref, None, "ERR:" + err))
            print("[%03d] ERROR %s" % (i, err), flush=True)
            continue
        pred = max(range(12), key=lambda k: logits[k])
        if pred == ref:
            matched += 1
        else:
            mism.append((i, ref, pred, None))
        if (i + 1) % 24 == 0 or i == n - 1:
            print("[%03d/%d] matched=%d rate=%.4f (%.1fs)" %
                  (i + 1, n, matched, matched / (i + 1), time.time() - t0), flush=True)
    rate = matched / n
    print("\n=== RESULT ===")
    print("matched=%d/%d match_rate=%.6f" % (matched, n, rate))
    print("mismatch_count=%d" % len([m for m in mism if m[3] is None]))
    # 前 20 条 mismatch 明细
    print("--- mismatch (first 20) ---")
    for m in mism[:20]:
        print("idx=%03d ref=%s pred=%s %s" % (m[0], m[1], m[2], m[3] or ""))
    print("--- confusion (ref -> pred) ---")
    conf = {}
    for m in mism:
        if m[3] is None:
            conf[(m[1], m[2])] = conf.get((m[1], m[2]), 0) + 1
    for (r, p), c in sorted(conf.items()):
        print("ref=%2d -> pred=%2d : %d" % (r, p, c))

if __name__ == "__main__":
    main()
