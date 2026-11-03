#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix10class24-full24-failed-rx-forceclass1 — 24 类双 SDR 失败 RX 强制分类（20 唯一 source_index）。

诊断专用离线管道（复用 rxresidual-audit1 的 canonical 恢复 + 分类链工具），对
`rml24_full24_failed_rx_1773374413.tar.gz` 里被生产门禁 0.100 排除的 20 个唯一
source_index 失败样本做：身份校验 -> canonical 强制分类导出 -> host BF16 前向（≥2 次），
回答「这 20 类失败样本是否仍产出 baseline 一致的 24 类预测」。

Phase:
  `--phase extract`   归档 SHA 校验 + 安全解包（拒绝绝对路径/..穿越/符号链接/硬链接/越界）
  `--phase inventory` 20 唯一 source_index 身份校验 + manifest 交叉核对 + 产出 inventory.tsv
  `--phase classify`  host BF16 强制分类（icraft-run.exe，≥2 前向）+ per_sample_results/raw24_logits/summary

红线：不碰板 / 不改生产 0.100 门限 / 不改恢复器 / 不改 runner / 不改模型 / 不改标签 /
      不改 canonical 资产 / 不改发射安全上限。20/20 正确也只能写
      EVIDENCE_SUPPORTS_PROSPECTIVE_GATE_RELAXATION，不写 NEW_PRODUCTION_THRESHOLD / RF_PASS。

注意：本脚本独立于 rxresidual-audit1 的 audit_fix10class24_failed_rx_forced_classification.py，
后者硬锁旧归档 SHA `08ef944e…` 的保护保持不动；本脚本只接受新归档 SHA `53b96312…`。
"""
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import numpy as np

# ----------------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------------
NEW_ARCHIVE_SHA256 = (
    "53b963127b5ae8575d660366ab193f02cf8339e6f6518ef769519fecf808e6ef"
)

# 归档中必须恰好出现的 20 个唯一 source_index（= 24 类清单去掉 4 个过 0.10 门的类：
# 4500=32APSK / 6000=16QAM / 8500=AM-SSB-WC / 11000=GMSK）。fail-closed：多/少/换都拒绝。
EXPECT_SOURCE_INDEXES = [
    0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 5000,
    5500, 6500, 7000, 7500, 8000, 9000, 9500, 10000, 10500, 11500,
]
EXPECT_SAMPLE_COUNT = len(EXPECT_SOURCE_INDEXES)  # 20

# 每个 failed_rx/<source_index>/ 下必须齐全的 7 个文件
REQUIRED_FILES = [
    "raw_rx_ci16le.bin",
    "expected_scaled_payload_ci16le.bin",
    "expected_full_burst_ci16le.bin",
    "coarse_corrected_rx_cf64le.bin",
    "recovered_payload_f32le.bin",
    "recovery_diagnostics.json",
    "SHA256SUMS.txt",
]

# recovery_diagnostics.json 必填字段（fail-closed）
REQUIRED_JSON_FIELDS = [
    "source_index",
    "target_rms",
    "tx_scale",
    "failure_enum",
    "payload_training_residual",
    "timing_offset",
    "coarse_cfo_hz",
    "fine_cfo_hz",
]

# clean24_smoke_manifest.tsv 27 列 schema（与 predict_rml24_bf16_baseline.py 一致）
MANIFEST_HEADER = [
    "sample_index", "source_index", "raw24_class", "deployed23_class",
    "modulation", "snr_db", "split_role", "global_K", "original_dc_i",
    "original_dc_q", "ac_rms", "rec_scale", "complex_count", "sample_rate",
    "tx_rms", "tx_peak", "clip_count", "edge_policy", "guard",
    "original_sha256", "quantized_sha256", "recovered_tensor_sha256",
    "quantized_file", "recovered_tensor_file",
    "tx_scale", "frozen_raw24_pred", "frozen_deployed23_pred",
]

# 冻结 BF16 baseline TSV（clean24_smoke_raw24_bf16_baseline.tsv）7 列
BASELINE_HEADER = ["source_index", "original_sha256", "raw24_class", "modulation",
                   "split_role", "frozen_bf16_raw24_pred", "model_sha256"]

NETWORK_NAME = "model_24class"
EXPECT_CLASS_COUNT = 24
HOST_LAYER = "HOST_BF16_FORCED_CLASSIFICATION"   # 非板端 NPU 实测

# 冻结 BF16 24 类模型身份（fail-closed：误跑错模型直接拒绝）
FROZEN_MODEL_JSON_SHA256 = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA256 = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

# ----------------------------------------------------------------------------
# 工具
# ----------------------------------------------------------------------------
def fail(msg):
    sys.stderr.write("FAIL-CLOSED: %s\n" % msg)
    sys.exit(1)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fix_nan_literals(text):
    """把字符串外的裸小写 nan/inf 字面量改成 JSON 合法的大写形式（板端 dump 含 snr_db=nan）。"""
    parts = re.split(r'("(?:[^"\\]|\\.)*")', text)
    for i, p in enumerate(parts):
        if p.startswith('"'):
            continue
        p = re.sub(r'\bnan\b', 'NaN', p)
        p = re.sub(r'\binf\b', 'Infinity', p)
        p = re.sub(r'\b-inf\b', '-Infinity', p)
        parts[i] = p
    return "".join(parts)


def load_json_nan_tolerant(path):
    """读 JSON，容忍 nan/Infinity/-Infinity 字面量。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = _fix_nan_literals(text)

    def _const(s):
        m = {
            "NaN": float("nan"),
            "Infinity": float("inf"),
            "-Infinity": float("-inf"),
        }
        if s in m:
            return m[s]
        raise ValueError("unexpected constant %r" % s)

    return json.loads(text, parse_constant=_const)


def parse_manifest(path):
    """读 27 列 manifest，返回 {source_index: row}。"""
    if not os.path.isfile(path):
        fail("manifest not found: %s" % path)
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f]
    header = lines[0].split("\t")
    if header != MANIFEST_HEADER:
        fail("manifest header not the 27-col clean24 schema (got %d cols)" % len(header))
    out = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != len(MANIFEST_HEADER):
            fail("manifest row has %d cols (want %d)" % (len(f), len(MANIFEST_HEADER)))
        row = dict(zip(MANIFEST_HEADER, f))
        sid = int(row["source_index"])
        if sid in out:
            fail("duplicate source_index=%d in manifest" % sid)
        out[sid] = row
    if len(out) != EXPECT_CLASS_COUNT:
        fail("manifest has %d rows (want %d)" % (len(out), EXPECT_CLASS_COUNT))
    return out


def read_tsv(path):
    if not os.path.isfile(path):
        fail("TSV not found: %s" % path)
    with open(path, "r", encoding="utf-8", newline="") as f:
        lines = [ln.rstrip("\n") for ln in f]
    if not lines:
        fail("empty TSV: %s" % path)
    header = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != len(header):
            fail("TSV %s row has %d cols (want %d)" % (path, len(f), len(header)))
        rows.append(dict(zip(header, f)))
    return header, rows


# ----------------------------------------------------------------------------
# 安全解包
# ----------------------------------------------------------------------------
def is_safe_member(m):
    name = m.name
    if name.startswith("/") or name.startswith("\\"):
        return False
    if len(name) >= 2 and name[1] == ":":
        return False
    parts = name.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        return False
    if m.issym() or m.islnk():
        return False
    return True


def dest_path(m, dest):
    return os.path.normpath(os.path.join(dest, m.name.replace("\\", "/")))


def phase_extract(archive, dest):
    if not os.path.isfile(archive):
        fail("archive not found: %s" % archive)
    got = sha256_of(archive)
    if got != NEW_ARCHIVE_SHA256:
        fail("archive SHA mismatch: got %s expected %s" % (got, NEW_ARCHIVE_SHA256))
    if os.path.exists(dest) and os.listdir(dest):
        fail("extract destination is non-empty; use a fresh empty directory: %s" % dest)
    os.makedirs(dest, exist_ok=True)

    dest_abs = os.path.abspath(dest)
    tf = tarfile.open(archive, "r:gz")
    members = tf.getmembers()
    for m in members:
        if not is_safe_member(m):
            fail("unsafe archive member rejected: %r" % m.name)
    for m in members:
        if m.isdir():
            continue
        p = dest_path(m, dest)
        if not os.path.abspath(p).startswith(dest_abs + os.sep):
            fail("member escapes destination: %r -> %s" % (m.name, p))
    for m in members:
        if not m.isdir():
            p = dest_path(m, dest)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            tf.extract(m, dest, filter="data")
    tf.close()
    print("EXTRACT_OK archive_sha256=%s members=%d dest=%s" % (got, len(members), dest))
    return 0


# ----------------------------------------------------------------------------
# inventory（平铺 failed_rx/<source_index>/）
# ----------------------------------------------------------------------------
def phase_inventory(captures_dir, manifest_path, out_dir):
    """captures_dir = 解包后的根（其下有 failed_rx/<source_index>/）。"""
    failed_rx = os.path.join(captures_dir, "failed_rx")
    if not os.path.isdir(failed_rx):
        fail("missing failed_rx dir under %s" % captures_dir)

    manifest = parse_manifest(manifest_path)

    dirs = sorted(d for d in os.listdir(failed_rx)
                  if os.path.isdir(os.path.join(failed_rx, d)))
    got_indexes = []
    for d in dirs:
        try:
            got_indexes.append(int(d))
        except ValueError:
            fail("non-numeric source_index dir: %r" % d)
    got_indexes = sorted(got_indexes)

    if got_indexes != EXPECT_SOURCE_INDEXES:
        fail("source_index set %s != expected 20 %s" % (got_indexes, EXPECT_SOURCE_INDEXES))
    if len(set(got_indexes)) != len(got_indexes):
        fail("duplicate source_index dirs detected")

    rows = []
    errors = []
    for sid in got_indexes:
        sdir = os.path.join(failed_rx, str(sid))
        # 7 文件齐全
        missing_files = [f for f in REQUIRED_FILES
                         if not os.path.isfile(os.path.join(sdir, f))]
        if missing_files:
            errors.append("%d missing files: %s" % (sid, missing_files))

        jpath = os.path.join(sdir, "recovery_diagnostics.json")
        if not os.path.isfile(jpath):
            errors.append("%d missing recovery_diagnostics.json" % sid)
            continue
        j = load_json_nan_tolerant(jpath)
        missing_fields = [f for f in REQUIRED_JSON_FIELDS if f not in j]
        if missing_fields:
            errors.append("%d JSON missing fields: %s" % (sid, missing_fields))
        if int(j.get("source_index", -1)) != sid:
            errors.append("%d JSON source_index %s mismatch" % (sid, j.get("source_index")))

        # raw_rx SHA 与 SHA256SUMS 一致
        raw_path = os.path.join(sdir, "raw_rx_ci16le.bin")
        sums_path = os.path.join(sdir, "SHA256SUMS.txt")
        raw_sha_ok = 0
        if os.path.isfile(raw_path) and os.path.isfile(sums_path):
            actual = sha256_of(raw_path)
            expected = None
            with open(sums_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2 and parts[1] == "raw_rx_ci16le.bin":
                        expected = parts[0]
            raw_sha_ok = 1 if (expected is not None and actual == expected) else 0
            if raw_sha_ok == 0:
                errors.append("%d raw_rx SHA mismatch: actual=%s expected=%s"
                              % (sid, actual, expected))
        else:
            errors.append("%d raw_rx or SHA256SUMS missing" % sid)

        # manifest 交叉核对：source_index 必须存在于 24 类清单，且 modulation/raw24_class 一致
        mrow = manifest.get(sid)
        if mrow is None:
            errors.append("%d not in 24-class manifest" % sid)
            mod = j.get("modulation", "")
            raw24 = j.get("raw24_class", "")
        else:
            mod = mrow["modulation"]
            raw24 = int(mrow["raw24_class"])
            if j.get("modulation", "") and j["modulation"] != mod:
                errors.append("%d JSON modulation %r != manifest %r"
                              % (sid, j["modulation"], mod))
            if j.get("raw24_class") is not None and int(j["raw24_class"]) != raw24:
                errors.append("%d JSON raw24_class %s != manifest %d"
                              % (sid, j["raw24_class"], raw24))

        rows.append({
            "source_index": sid,
            "modulation": mod,
            "raw24_class": raw24,
            "failure": j.get("failure", ""),
            "failure_enum": j.get("failure_enum", ""),
            "payload_training_residual": j.get("payload_training_residual", ""),
            "payload_training_corr": j.get("payload_training_corr", ""),
            "timing_offset": j.get("timing_offset", ""),
            "coarse_cfo_hz": j.get("coarse_cfo_hz", ""),
            "fine_cfo_hz": j.get("fine_cfo_hz", ""),
            "target_rms": j.get("target_rms", ""),
            "tx_scale": j.get("tx_scale", ""),
            "raw_rx_sha256": j.get("raw_rx_sha256", ""),
            "raw_rx_sha_ok": raw_sha_ok,
            "files_present": "%d/%d" % (len(REQUIRED_FILES) - len(missing_files),
                                        len(REQUIRED_FILES)),
        })

    if errors:
        for e in errors:
            sys.stderr.write("ERROR: %s\n" % e)
        fail("inventory verification failed with %d error(s)" % len(errors))

    n = len(rows)
    if n != EXPECT_SAMPLE_COUNT:
        fail("stop condition unmet: samples=%d (want %d)" % (n, EXPECT_SAMPLE_COUNT))

    os.makedirs(out_dir, exist_ok=True)
    cols = ["source_index", "modulation", "raw24_class", "failure", "failure_enum",
            "payload_training_residual", "payload_training_corr", "timing_offset",
            "coarse_cfo_hz", "fine_cfo_hz", "target_rms", "tx_scale", "raw_rx_sha256",
            "raw_rx_sha_ok", "files_present"]
    out_path = os.path.join(out_dir, "inventory.tsv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in sorted(rows, key=lambda r: r["source_index"]):
            f.write("\t".join(str(r[c]) for c in cols) + "\n")

    print("INVENTORY_OK samples=%d out=%s" % (n, out_path))
    return 0


# ----------------------------------------------------------------------------
# classify（host BF16 强制分类）
# ----------------------------------------------------------------------------
def run_host_infer(icraft_run, model_json, model_raw, input_bin, workdir):
    """跑 icraft-run Host 后端，返回 (raw_bytes, logits_fp32_ndarray)。"""
    log_path = workdir / "logs"
    cmd = [
        str(icraft_run),
        "--json", str(model_json),
        "--raw", str(model_raw),
        "--network", NETWORK_NAME,
        "--input", str(input_bin),
        "--backends", "Host",
        "--dump_output",
        "--log_path", str(log_path),
    ]
    proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True)
    if proc.returncode != 0:
        fail("icraft-run exit %d: %s" % (proc.returncode,
                                          proc.stderr.decode("utf-8", "replace")[-2000:]))
    ftmp_dir = log_path / NETWORK_NAME / "ftmpHQB"
    ftmps = list(ftmp_dir.glob("*.ftmp")) if ftmp_dir.is_dir() else []
    if len(ftmps) != 1:
        fail("expected exactly 1 ftmp under %s, got %d" % (ftmp_dir, len(ftmps)))
    raw = ftmps[0].read_bytes()
    if len(raw) != EXPECT_CLASS_COUNT * 4:
        fail("ftmp %s is %d bytes (want %d)" % (ftmps[0].name, len(raw),
                                                EXPECT_CLASS_COUNT * 4))
    logits = np.frombuffer(raw, dtype="<f4").astype(np.float64)
    return raw, logits


def classify_one_sample(icraft_run, model_json, model_raw, input_bin, n_passes=2):
    passes = []
    for _ in range(n_passes):
        with tempfile.TemporaryDirectory() as td:
            raw, logits = run_host_infer(icraft_run, model_json, model_raw,
                                         input_bin, Path(td))
        passes.append({
            "raw": raw,
            "logits": logits,
            "argmax": int(np.argmax(logits)),
            "finite": bool(np.all(np.isfinite(logits))),
        })
    return passes


def phase_classify(args):
    icraft_run = Path(args.icraft_run) if args.icraft_run else None
    model_dir = Path(args.model_dir) if args.model_dir else None
    forced_dir = args.forced_classify_dir
    baseline_path = args.baseline
    manifest_path = args.manifest
    out_dir = args.out_dir or "results/full24_failed_rx_forceclass"

    if not icraft_run or not icraft_run.is_file():
        fail("--icraft-run not found")
    if not model_dir:
        fail("--model-dir required")
    model_json = model_dir / "rml24_adamrv11_bf16.json"
    model_raw = model_dir / "rml24_adamrv11_bf16.raw"
    if not model_json.is_file() or not model_raw.is_file():
        fail("model json/raw not found under %s" % model_dir)
    if sha256_of(str(model_json)) != FROZEN_MODEL_JSON_SHA256:
        fail("model json SHA mismatch (not the frozen BF16 model): %s" % model_json)
    if sha256_of(str(model_raw)) != FROZEN_MODEL_RAW_SHA256:
        fail("model raw SHA mismatch (not the frozen BF16 model): %s" % model_raw)
    if not forced_dir or not os.path.isdir(forced_dir):
        fail("--forced-classify-dir not found: %s" % forced_dir)
    if not baseline_path or not os.path.isfile(baseline_path):
        fail("--baseline not found")

    manifest = parse_manifest(manifest_path)

    # 冻结 BF16 baseline：source_index -> frozen_bf16_raw24_pred
    _, b_rows = read_tsv(baseline_path)
    baseline_pred = {}
    for r in b_rows:
        baseline_pred[int(r["source_index"])] = int(r["frozen_bf16_raw24_pred"])
    missing = [s for s in EXPECT_SOURCE_INDEXES if s not in baseline_pred]
    if missing:
        fail("baseline missing source_index=%s" % missing)

    # 收集导出目录（forced_classify_export/<capture_id>/<source_index>/）
    samples = []
    for cap in sorted(os.listdir(forced_dir)):
        cap_path = os.path.join(forced_dir, cap)
        if not os.path.isdir(cap_path):
            continue
        for idx in sorted(os.listdir(cap_path)):
            idx_path = os.path.join(cap_path, idx)
            if not os.path.isdir(idx_path):
                continue
            mi = os.path.join(idx_path, "model_input_f32le.bin")
            jp = os.path.join(idx_path, "forced_recovery.json")
            if not os.path.isfile(mi) or not os.path.isfile(jp):
                fail("export dir missing model_input/forced_recovery.json: %s" % idx_path)
            j = load_json_nan_tolerant(jp)
            samples.append((cap, int(idx), idx_path, mi, j))

    if len(samples) != EXPECT_SAMPLE_COUNT:
        fail("expected %d exported samples, got %d" % (EXPECT_SAMPLE_COUNT, len(samples)))
    keys = set()
    for cap, idx, _, _, _ in samples:
        if idx in keys:
            fail("duplicate export source_index: %d" % idx)
        keys.add(idx)
    if keys != set(EXPECT_SOURCE_INDEXES):
        fail("export source_index set %s != expected 20" % sorted(keys))

    logit_rows = []
    result_rows = []
    for cap, idx, idx_path, mi, j in sorted(samples, key=lambda s: s[1]):
        mi_bytes = open(mi, "rb").read()
        if len(mi_bytes) != 2 * 1024 * 4:
            fail("model_input_f32le.bin size %d != 8192: %s" % (len(mi_bytes), mi))
        mi_arr = np.frombuffer(mi_bytes, dtype="<f4")
        input_finite = bool(np.all(np.isfinite(mi_arr)))

        passes = classify_one_sample(icraft_run, model_json, model_raw, Path(mi), n_passes=2)

        mrow = manifest[idx]
        sc = int(mrow["raw24_class"])
        mod = mrow["modulation"]
        # forced_recovery.json 的 source_class 必须与 manifest raw24_class 一致
        if int(j["source_class"]) != sc:
            fail("source_index=%d forced_recovery source_class %d != manifest %d"
                 % (idx, int(j["source_class"]), sc))

        bpred = baseline_pred.get(idx)
        if bpred is None:
            fail("baseline has no source_index=%d" % idx)

        p1, p2 = passes[0], passes[1]
        pred1 = p1["argmax"]
        pred2 = p2["argmax"]
        baseline_agreement = 1 if pred1 == bpred else 0
        label_correct = 1 if pred1 == sc else 0
        finite = 1 if (p1["finite"] and p2["finite"] and input_finite) else 0
        repeat_argmax = 1 if pred1 == pred2 else 0
        repeat_logits_byte = 1 if p1["raw"] == p2["raw"] else 0

        top1 = float(np.max(p1["logits"]))
        sorted_logits = np.sort(p1["logits"])[::-1]
        top2 = float(sorted_logits[1]) if len(sorted_logits) > 1 else float("nan")
        margin = float(sorted_logits[0] - sorted_logits[1]) if len(sorted_logits) > 1 else float("nan")

        logit_rows.append({
            "source_index": idx,
            "source_class": sc,
            **{"logit_%02d" % k: ("%.17g" % p1["logits"][k]) for k in range(EXPECT_CLASS_COUNT)},
            "raw24_pred_pass1": pred1,
            "raw24_pred_pass2": pred2,
        })

        result_rows.append({
            "source_index": idx,
            "source_class": sc,
            "modulation": mod,
            "baseline_pred": bpred,
            "raw24_pred_pass1": pred1,
            "raw24_pred_pass2": pred2,
            "baseline_agreement": baseline_agreement,
            "label_correct": label_correct,
            "finite": finite,
            "repeat_argmax_deterministic": repeat_argmax,
            "repeat_logits_byte_identical": repeat_logits_byte,
            "top1_logit": "%.9g" % top1,
            "top2_logit": "%.9g" % top2,
            "margin": "%.9g" % margin,
            "payload_training_residual": j.get("payload_training_residual", ""),
            "payload_training_corr": j.get("payload_training_corr", ""),
            "raw_rx_sha256": j.get("raw_rx_sha256", ""),
            "model_input_sha256": hashlib.sha256(mi_bytes).hexdigest(),
            "result_layer": HOST_LAYER,
        })

    os.makedirs(out_dir, exist_ok=True)

    logit_cols = ["source_index", "source_class"] + \
                 ["logit_%02d" % k for k in range(EXPECT_CLASS_COUNT)] + \
                 ["raw24_pred_pass1", "raw24_pred_pass2"]
    with open(os.path.join(out_dir, "raw24_logits.tsv"), "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(logit_cols) + "\n")
        for r in sorted(logit_rows, key=lambda r: r["source_index"]):
            f.write("\t".join(str(r[c]) for c in logit_cols) + "\n")

    res_cols = ["source_index", "source_class", "modulation", "baseline_pred",
                "raw24_pred_pass1", "raw24_pred_pass2", "baseline_agreement", "label_correct",
                "finite", "repeat_argmax_deterministic", "repeat_logits_byte_identical",
                "top1_logit", "top2_logit", "margin", "payload_training_residual",
                "payload_training_corr", "raw_rx_sha256", "model_input_sha256", "result_layer"]
    with open(os.path.join(out_dir, "per_sample_results.tsv"), "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(res_cols) + "\n")
        for r in sorted(result_rows, key=lambda r: r["source_index"]):
            f.write("\t".join(str(r[c]) for c in res_cols) + "\n")

    n = len(result_rows)
    n_agree = sum(r["baseline_agreement"] for r in result_rows)
    n_correct = sum(r["label_correct"] for r in result_rows)
    n_finite = sum(r["finite"] for r in result_rows)
    n_repeat_argmax = sum(r["repeat_argmax_deterministic"] for r in result_rows)
    n_repeat_byte = sum(r["repeat_logits_byte_identical"] for r in result_rows)

    # 结论：20/20 正确 -> 仅支持「前瞻验证」（上限）；否则（有误分类）-> 证据反对放宽。
    # 关键：被 0.10 门拒绝的样本里出现误分类，说明该门并非过度保守，放宽会接纳已知误分类样本。
    all_correct = (n_correct == n and n_agree == n and n_finite == n)
    misclassified = [r["source_index"] for r in result_rows
                     if int(r["label_correct"]) == 0]
    if all_correct:
        conclusion = "EVIDENCE_SUPPORTS_PROSPECTIVE_GATE_RELAXATION"
    else:
        conclusion = "EVIDENCE_AGAINST_GATE_RELAXATION"

    summary = {
        "task_id": "fix10class24-full24-failed-rx-forceclass1",
        "status": "M29-RML24-FULL24-FAILED-RX-FORCECLASS1-AUDIT-COMPLETE",
        "result_layer": HOST_LAYER,
        "archive_sha256": NEW_ARCHIVE_SHA256,
        "sample_count": n,
        "source_indexes": EXPECT_SOURCE_INDEXES,
        "baseline_agreement": "%d/%d" % (n_agree, n),
        "label_correct": "%d/%d" % (n_correct, n),
        "finite": "%d/%d" % (n_finite, n),
        "repeat_argmax_deterministic": "%d/%d" % (n_repeat_argmax, n),
        "repeat_logits_byte_identical": "%d/%d" % (n_repeat_byte, n),
        "misclassified_samples": n - n_correct,
        "misclassified_source_indexes": misclassified,
        "production_gate_modified": 0,
        "production_threshold": 0.100,
        "conclusion": conclusion,
        "selection_bias": "FAILURE_CONDITIONAL_SAMPLE",
        "per_sample": [{
            "source_index": r["source_index"],
            "source_class": r["source_class"],
            "modulation": r["modulation"],
            "baseline_pred": r["baseline_pred"],
            "raw24_pred_pass1": r["raw24_pred_pass1"],
            "baseline_agreement": r["baseline_agreement"],
            "label_correct": r["label_correct"],
            "finite": r["finite"],
            "repeat_argmax_deterministic": r["repeat_argmax_deterministic"],
            "repeat_logits_byte_identical": r["repeat_logits_byte_identical"],
            "payload_training_residual": r["payload_training_residual"],
            "payload_training_corr": r["payload_training_corr"],
        } for r in sorted(result_rows, key=lambda r: r["source_index"])],
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8", newline="") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")

    print("CLASSIFY_OK samples=%d baseline_agreement=%d/%d label_correct=%d/%d "
          "finite=%d/%d repeat_argmax=%d/%d repeat_logits_byte=%d/%d layer=%s "
          "conclusion=%s" %
          (n, n_agree, n, n_correct, n, n_finite, n, n_repeat_argmax, n,
           n_repeat_byte, n, HOST_LAYER, conclusion))
    return 0


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="fix10class24-full24-failed-rx-forceclass1")
    ap.add_argument("--phase", required=True, choices=["extract", "inventory", "classify"])
    ap.add_argument("--archive", help="rml24_full24_failed_rx tar.gz path (extract)")
    ap.add_argument("--dest", help="fresh extraction destination dir (extract)")
    ap.add_argument("--captures-dir", help="extracted root (inventory)")
    ap.add_argument("--manifest", help="clean24_smoke_manifest.tsv path (inventory/classify)")
    ap.add_argument("--out-dir", help="results dir (inventory/classify)")
    ap.add_argument("--forced-classify-dir", help="forced_classify_export dir (classify)")
    ap.add_argument("--baseline", help="clean24_smoke_raw24_bf16_baseline.tsv (classify)")
    ap.add_argument("--icraft-run", help="path to icraft-run.exe (classify)")
    ap.add_argument("--model-dir", help="BF16 model dir (classify)")
    args = ap.parse_args()

    if args.phase == "extract":
        if not args.archive or not args.dest:
            ap.error("--phase extract requires --archive and --dest")
        return phase_extract(args.archive, args.dest)

    if args.phase == "inventory":
        if not args.captures_dir or not args.manifest or not args.out_dir:
            ap.error("--phase inventory requires --captures-dir, --manifest, --out-dir")
        return phase_inventory(args.captures_dir, args.manifest, args.out_dir)

    if args.phase == "classify":
        return phase_classify(args)

    ap.error("unknown phase %s" % args.phase)


if __name__ == "__main__":
    sys.exit(main())
