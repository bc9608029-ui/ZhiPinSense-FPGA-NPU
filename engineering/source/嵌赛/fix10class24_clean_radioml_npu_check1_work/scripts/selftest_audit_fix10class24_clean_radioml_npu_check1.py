#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
selftest_audit_fix10class24_clean_radioml_npu_check1.py

自测 audit_fix10class24_clean_radioml_npu_check1.py 的 fail-closed 行为：
在合成夹具上断言每种场景的退出码。夹具的 manifest/baseline 用真实冻结文件
（只读），仅结果 TSV/summary.json 由本脚本合成。

场景:
  S1  clean 24/24          -> rc 0
  S2  1 个分类错误         -> rc 0（测量合法，报告错误）
  S3  合法 1 excluded      -> rc 0（分母仍 24）
  S4  从分母删 1 行(23行)  -> rc 1（硬门禁：总行数 != 24）
  S5  source_index 篡改    -> rc 1
  S6  baseline_pred 篡改   -> rc 1
  S7  nan_or_inf>0         -> rc 1
  S8  repeat_deterministic<24 -> rc 1
  S9  summary.json 数值不一致 -> rc 1
  S10 summary.json 模型 sha 不符 -> rc 1

用法（Windows: python）:
  python selftest_audit_fix10class24_clean_radioml_npu_check1.py \
      --frozen-dir <clean24_smoke> --baseline <baseline.tsv>
退出码 0 = 全部断言通过。
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

AUDIT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "audit_fix10class24_clean_radioml_npu_check1.py")
FROZEN_MODEL_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

HEADER = "\t".join(["file_name", "source_index", "raw24_class", "modulation", "snr_db",
                    "split_role", "valid", "raw24_pred", "baseline_pred", "correct",
                    "prediction_agreement", "repeat_deterministic", "window_corr",
                    "window_nmse", "delay_offset", "verdict"])


def _lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return [ln.rstrip("\r\n") for ln in f]


def load_manifest(frozen_dir):
    out = {}
    for ln in _lines(os.path.join(frozen_dir, "route_d2_rf_manifest.tsv"))[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        out[int(f[1])] = (int(f[2]), f[4])
    return out


def load_baseline(baseline_path):
    out = {}
    for ln in _lines(baseline_path)[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        out[int(f[0])] = int(f[5])
    return out


def row(fname, sid, cls, mod, pred, bpred, correct, agr, rdet, valid=1,
        verdict="CLEAN_DIGITAL_SCORED"):
    return "\t".join([fname, str(sid), str(cls), mod, "nan", "holdout",
                      str(valid), str(pred), str(bpred), str(correct), str(agr),
                      str(rdet), "0.9999", "0.0001", "0", verdict])


def build_results(manifest, baseline, scenario, out_dir):
    sids = sorted(manifest)
    rows = []
    for sid in sids:
        cls, mod = manifest[sid]
        bpred = baseline[sid]
        correct = 1
        pred = cls
        agr = 1 if pred == bpred else 0
        rdet = 1
        valid = 1
        if scenario == "S2_error" and sid == sids[3]:
            pred = (cls + 1) % 24
            correct = 0
            agr = 1 if pred == bpred else 0
        if scenario == "S5_bad_sid" and sid == sids[5]:
            sid = sid + 1
        if scenario == "S6_bad_baseline_pred" and sid == sids[6]:
            # 结果里 baseline_pred 列被写成非冻结值
            rows.append("\t".join(["f_%d" % sid, str(sid), str(cls), mod, "nan",
                                   "holdout", str(valid), str(pred), str(bpred + 1),
                                   str(correct), "0", str(rdet), "0.9999", "0.0001",
                                   "0", "CLEAN_DIGITAL_SCORED"]))
            continue
        if scenario == "S7_nan" and sid == sids[7]:
            valid = 0
            pred = -1
            correct = 0
            agr = 0
            rdet = 0
        if scenario == "S8_nondeterministic" and sid == sids[8]:
            rdet = 0
        rows.append(row("f_%d" % sid, sid, cls, mod, pred, bpred, correct, agr,
                        rdet, valid=valid))

    if scenario == "S3_excluded":
        # 把最后一个样本改成合法 excluded（仍保留 24 行、分母不删）
        sid = sids[-1]
        cls, mod = manifest[sid]
        rows[-1] = "\t".join(["f_%d" % sid, str(sid), str(cls), mod, "nan",
                              "holdout", "0", "-1", "-1", "-1", "-1", "-1",
                              "0.5", "0.1", "0", "CLEAN_NO_VALID_WINDOW"])
    elif scenario == "S4_drop_row":
        rows = rows[:-1]  # 23 行，把 excluded 从分母删掉

    with open(os.path.join(out_dir, "route_f_fix10class24_bf16_clean_iq_results.tsv"),
              "w", encoding="utf-8", newline="\n") as f:
        f.write(HEADER + "\n")
        f.write("\n".join(rows) + "\n")

    # summary.json（S9/S10 制造不一致）
    if scenario in ("S9_bad_summary", "S10_bad_sha"):
        scored = sum(1 for r in rows if r.split("\t")[-1] == "CLEAN_DIGITAL_SCORED")
        excluded = len(rows) - scored
        summary = {
            "token": "x", "measurement_token": "x",
            "model_domain_token": "x", "deployment_mode": "raw24",
            "model_mode": "bf16", "input_kind": "radioml-d2-2p56m",
            "frozen_dir": "", "model_sha": FROZEN_MODEL_RAW_SHA,
            "baseline_path": "", "baseline_rows": 24, "baseline_identity_ok": True,
            "holdout_files": 24, "scored": scored, "excluded": excluded,
            "prediction_agreement": 0.0, "label_accuracy": 0.0, "macro_accuracy": 0.0,
            "wc_total": 1, "wc_correct": 1, "sc_total": 1, "sc_correct": 1,
            "nan_or_inf": 0, "repeat_deterministic": scored, "exclude_reasons": {},
        }
        if scenario == "S9_bad_summary":
            summary["scored"] = scored + 1  # 与逐样本不一致
        if scenario == "S10_bad_sha":
            summary["model_sha"] = "0" * 64
        with open(os.path.join(out_dir, "route_f_fix10class24_bf16_clean_iq_summary.json"),
                  "w", encoding="utf-8") as f:
            json_dump(summary, f)


def json_dump(obj, f):
    import json
    json.dump(obj, f)


def run_audit(frozen_dir, baseline_path, out_dir):
    r = subprocess.run([sys.executable, AUDIT, "--out-dir", out_dir,
                        "--frozen-dir", frozen_dir, "--baseline", baseline_path],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen-dir", required=True)
    ap.add_argument("--baseline", required=True)
    args = ap.parse_args()

    manifest = load_manifest(args.frozen_dir)
    baseline = load_baseline(args.baseline)
    assert len(manifest) == 24 and len(baseline) == 24

    expected = {
        "S1_clean24": 0,
        "S2_error": 0,
        "S3_excluded": 0,
        "S4_drop_row": 1,
        "S5_bad_sid": 1,
        "S6_bad_baseline_pred": 1,
        "S7_nan": 1,
        "S8_nondeterministic": 1,
        "S9_bad_summary": 1,
        "S10_bad_sha": 1,
    }
    failures = 0
    tmp = tempfile.mkdtemp(prefix="clean_npu_check1_selftest_")
    try:
        for scenario, want_rc in expected.items():
            out_dir = os.path.join(tmp, scenario)
            os.makedirs(out_dir)
            build_results(manifest, baseline, scenario, out_dir)
            rc, so, se = run_audit(args.frozen_dir, args.baseline, out_dir)
            ok = (rc == want_rc)
            status = "OK " if ok else "FAIL"
            if not ok:
                failures += 1
            print("%s %-22s rc=%d (want %d)" % (status, scenario, rc, want_rc))
            if not ok:
                print("    stdout tail: %s" % so.strip().splitlines()[-1] if so.strip() else "(empty)")
                print("    stderr tail: %s" % se.strip().splitlines()[-1] if se.strip() else "(empty)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("-" * 60)
    if failures:
        print("SELF_TEST_FAIL %d/%d" % (failures, len(expected)))
        sys.exit(1)
    print("SELF_TEST_OK %d/%d" % (len(expected), len(expected)))
    sys.exit(0)


if __name__ == "__main__":
    main()
