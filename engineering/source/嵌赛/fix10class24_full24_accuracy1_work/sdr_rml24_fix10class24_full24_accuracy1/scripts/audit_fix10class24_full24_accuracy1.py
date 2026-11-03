#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix10class24-full24-accuracy1 — 24 类真实 RF 样本「最新系统到底识别对多少个」。

用 rxrecovery1（FULL `6fd93f78…`）在板端采集 24 个 raw24 类各 1 个真实双 SDR 样本，
本脚本离线编排 Phase B/C：
  Phase B  对被生产门 0.100 拒绝的样本：canonical 强制分类导出（scalar + wide-linear
           两套 provisional model input）-> 冻结 BF16 离线前向 -> HOST_BF16_FORCED_DIAGNOSTIC。
  Phase C  三套指标 + 24×24 混淆 + 结论（A/B/C 决策规则）。

三套指标（全部如实报告，不得用标签选择 scalar/wide-linear）：
  (1) end_to_end_correct/24           —— 被门拒 = 失败（gated 且正确才计数）。
  (2) gated_correct/scored + coverage —— 仅统计过门样本。
  (3) forced full coverage           —— scalar_forced_correct/24 + wide_linear_forced_correct/24。

决策规则（主决策固定用 wide-linear，因为那是 rxrecovery1 实际部署的恢复路径；
scalar 仅作透明对照，绝不用标签挑哪个正确）：
  A) 全 24/24 正确 -> MODEL_RF_ACCURACY_PROVISIONALLY_SUPPORTED
  B) 任一 <24/24   -> MODEL_RF_ROBUSTNESS_INSUFFICIENT
  C) 输入不可重放 -> FULL24_ACCURACY_AUDIT_BLOCKED

Phase:
  `--phase inventory` 校验板端产物（24 行结果 TSV + 被拒样本 7 文件 dump 身份）-> inventory.tsv
  `--phase classify`  读板端结果 + forced-classify 导出 -> host BF16（scalar+wide-linear）->
                      三套指标 + 5 交付物

红线：不碰板 / 不改 0.100 门 / 不改恢复器 / 不改 runner / 不改模型 json·raw /
      不改标签序 / 不改 24→23 合同 / 不改 canonical 资产 / 不改 TX 安全上限。
      即使 24/24 也禁写 RF_PASS / SMOKE_PASS / NEW_PRODUCTION_THRESHOLD。
"""
import argparse
import hashlib
import json
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
# rxrecovery1 基线 FULL 包 SHA（本任务不做包，仅作身份锚点记录）
BASELINE_FULL_SHA256 = "6fd93f780770401056fe5c3717cf819238b1c5a0b25ed668425656b3654d6a36"

# 本轮 24 类真实 RF 采集归档（板端 --out-dir 整树 tar.gz；fail-closed 校验）。
ARCHIVE_SHA256 = "93ecb5e22a0c885065193ef64f7b522feef67cd1be821e8998158456451d7b7b"

# 24 个 source_index（= 24 raw24 类各 1 样本；AM-SSB WC/SC 独立）。
SOURCE_INDEX_TO_CLASS = {
    0: 0, 500: 1, 1000: 2, 1500: 3, 2000: 4, 2500: 5, 3000: 6, 3500: 7,
    4000: 8, 4500: 9, 5000: 10, 5500: 11, 6000: 12, 6500: 13, 7000: 14,
    7500: 15, 8000: 16, 8500: 17, 9000: 18, 9500: 19, 10000: 20, 10500: 21,
    11000: 22, 11500: 23,
}
EXPECT_SOURCE_INDEXES = sorted(SOURCE_INDEX_TO_CLASS)
EXPECT_SAMPLE_COUNT = len(EXPECT_SOURCE_INDEXES)  # 24

# 24 类标签顺序（冻结，与 rml24_raw.hpp kLabelOrder24 一致）。
LABEL_ORDER_24 = [
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
]

# 板端结果 TSV 22 列（iq_pc_tx_board_rx_24class_bf16_fix10.hpp:682）。
BOARD_RESULTS_HEADER = [
    "file_name", "source_index", "raw24_class", "modulation", "snr_db",
    "split_role", "valid", "raw24_pred", "baseline_pred", "correct",
    "prediction_agreement", "repeat_deterministic", "training_corr",
    "training_residual", "timing_offset", "gain_mag", "phase_deg",
    "coarse_cfo_hz", "fine_cfo_hz", "total_cfo_hz", "sro_ppm", "rf_verdict",
]

# 被门拒样本 failed_rx/<source_index>/ 下必须齐全的 7 个文件。
REQUIRED_FILES = [
    "raw_rx_ci16le.bin",
    "expected_scaled_payload_ci16le.bin",
    "expected_full_burst_ci16le.bin",
    "coarse_corrected_rx_cf64le.bin",
    "recovered_payload_f32le.bin",
    "recovery_diagnostics.json",
    "SHA256SUMS.txt",
]

# recovery_diagnostics.json 必填字段（fail-closed）。
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

# clean24_smoke_manifest.tsv 27 列 schema。
MANIFEST_HEADER = [
    "sample_index", "source_index", "raw24_class", "deployed23_class",
    "modulation", "snr_db", "split_role", "global_K", "original_dc_i",
    "original_dc_q", "ac_rms", "rec_scale", "complex_count", "sample_rate",
    "tx_rms", "tx_peak", "clip_count", "edge_policy", "guard",
    "original_sha256", "quantized_sha256", "recovered_tensor_sha256",
    "quantized_file", "recovered_tensor_file",
    "tx_scale", "frozen_raw24_pred", "frozen_deployed23_pred",
]

NETWORK_NAME = "model_24class"
EXPECT_CLASS_COUNT = 24
BOARD_LAYER = "BOARD_NPU_GATED_CLASSIFICATION"     # 板端 NPU 过门实测
HOST_LAYER = "HOST_BF16_FORCED_DIAGNOSTIC"         # 非板端 NPU 强制分类

GATE_VERDICT = "RF_PRESERVES_IQ"                    # 生产门通过的唯一判定

# 冻结 BF16 24 类模型身份（fail-closed：误跑错模型直接拒绝）。
FROZEN_MODEL_JSON_SHA256 = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA256 = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

MODEL_INPUT_BYTES = 2 * 1024 * 4  # [2,1024] fp32 = 8192 bytes

CONCL_SUPPORTED = "MODEL_RF_ACCURACY_PROVISIONALLY_SUPPORTED"
CONCL_INSUFFICIENT = "MODEL_RF_ROBUSTNESS_INSUFFICIENT"
CONCL_BLOCKED = "FULL24_ACCURACY_AUDIT_BLOCKED"


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
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = _fix_nan_literals(text)

    def _const(s):
        m = {"NaN": float("nan"), "Infinity": float("inf"),
             "-Infinity": float("-inf")}
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
# 安全解包（校验归档 SHA + 拒绝路径穿越/链接/越界）
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
    if got != ARCHIVE_SHA256:
        fail("archive SHA mismatch: got %s expected %s" % (got, ARCHIVE_SHA256))
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


def locate_board_results(captures_dir):
    """在板端产物目录找唯一 *_results.tsv。"""
    if not os.path.isdir(captures_dir):
        fail("captures dir not found: %s" % captures_dir)
    candidates = sorted(
        f for f in os.listdir(captures_dir)
        if f.endswith("_results.tsv") and os.path.isfile(os.path.join(captures_dir, f)))
    if len(candidates) != 1:
        fail("expected exactly 1 *_results.tsv under %s, got %d (%s)"
             % (captures_dir, len(candidates), candidates))
    return os.path.join(captures_dir, candidates[0])


def parse_board_results(path):
    """读板端结果 TSV，返回 {source_index: row}（fail-closed 校验 24 类齐全）。"""
    header, rows = read_tsv(path)
    if header != BOARD_RESULTS_HEADER:
        fail("board results header mismatch (got %d cols)" % len(header))
    out = {}
    for r in rows:
        sid = int(r["source_index"])
        if sid in out:
            fail("duplicate source_index=%d in board results" % sid)
        out[sid] = r
    if set(out) != set(EXPECT_SOURCE_INDEXES):
        fail("board results source_index set %s != expected 24 %s"
             % (sorted(out), EXPECT_SOURCE_INDEXES))
    return out


def capture_id_of(captures_dir):
    cid = os.path.basename(os.path.abspath(captures_dir))
    if not cid:
        fail("cannot derive capture_id from captures dir: %s" % captures_dir)
    return cid


# ----------------------------------------------------------------------------
# host BF16 前向（icraft-run Host 后端）
# ----------------------------------------------------------------------------
def run_host_infer(icraft_run, model_json, model_raw, input_bin, workdir):
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
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


def infer_one(icraft_run, model_json, model_raw, input_bin):
    """返回 (logits_fp64, argmax, finite)。"""
    with tempfile.TemporaryDirectory() as td:
        logits = run_host_infer(icraft_run, model_json, model_raw,
                                Path(input_bin), Path(td))
    return logits, int(np.argmax(logits)), bool(np.all(np.isfinite(logits)))


# ----------------------------------------------------------------------------
# 指标 + 决策（纯逻辑，可单测）
# ----------------------------------------------------------------------------
def compute_metrics(samples):
    """samples = 已解析的 24 个逐样本 dict。返回 metrics dict。"""
    n = len(samples)
    gated = [s for s in samples if s["gated"] == 1]
    gated_count = len(gated)
    rejected_count = n - gated_count

    end_to_end_correct = sum(s["end_to_end_correct"] for s in samples)
    scored = gated_count
    gated_correct = sum(1 for s in gated if s["board_label_correct"] == 1)
    coverage = (gated_count / n) if n else 0.0
    scalar_forced_correct = sum(s["scalar_label_correct"] for s in samples)
    wide_linear_forced_correct = sum(s["wl_label_correct"] for s in samples)
    forced_correct = sum(s["forced_label_correct"] for s in samples)
    logit_finite_count = sum(s["logit_finite"] for s in samples)

    blocked = any(s.get("blocked_reason") for s in samples)
    blocked_reasons = sorted({s["blocked_reason"] for s in samples
                              if s.get("blocked_reason")})

    scalar_wl_disagree = sum(
        1 for s in samples
        if s["scalar_label_correct"] != s["wl_label_correct"])

    # 主决策固定用 wide-linear（rxrecovery1 实际部署的恢复路径）。
    if blocked:
        conclusion = CONCL_BLOCKED
    elif wide_linear_forced_correct == n:
        conclusion = CONCL_SUPPORTED
    else:
        conclusion = CONCL_INSUFFICIENT

    # 24×24 混淆（用主 forced 答案：gated=板端 argmax，rejected=wide-linear(适用)/scalar）。
    confusion = [[0] * EXPECT_CLASS_COUNT for _ in range(EXPECT_CLASS_COUNT)]
    for s in samples:
        sc = s["source_class"]
        p = s["forced_raw24_pred"]
        if 0 <= sc < EXPECT_CLASS_COUNT and 0 <= p < EXPECT_CLASS_COUNT:
            confusion[sc][p] += 1

    return {
        "sample_count": n,
        "gated_count": gated_count,
        "rejected_count": rejected_count,
        "end_to_end_correct": "%d/%d" % (end_to_end_correct, n),
        "end_to_end_accuracy": round(end_to_end_correct / n, 6) if n else 0.0,
        "scored": scored,
        "gated_correct": "%d/%d" % (gated_correct, scored),
        "coverage": round(coverage, 6),
        "gated_accuracy": round(gated_correct / scored, 6) if scored else None,
        "scalar_forced_correct": "%d/%d" % (scalar_forced_correct, n),
        "wide_linear_forced_correct": "%d/%d" % (wide_linear_forced_correct, n),
        "forced_correct": "%d/%d" % (forced_correct, n),
        "logit_finite": "%d/%d" % (logit_finite_count, n),
        "scalar_wide_linear_disagree": scalar_wl_disagree,
        "blocked": blocked,
        "blocked_reasons": blocked_reasons,
        "conclusion": conclusion,
        "confusion_24": confusion,
    }


# ----------------------------------------------------------------------------
# inventory：校验板端产物
# ----------------------------------------------------------------------------
def phase_inventory(captures_dir, manifest_path, out_dir):
    manifest = parse_manifest(manifest_path)
    board_path = locate_board_results(captures_dir)
    board = parse_board_results(board_path)

    failed_rx = os.path.join(captures_dir, "failed_rx")
    dirs = []
    if os.path.isdir(failed_rx):
        for d in sorted(os.listdir(failed_rx)):
            p = os.path.join(failed_rx, d)
            if os.path.isdir(p):
                dirs.append(d)

    rows = []
    errors = []
    for sid in EXPECT_SOURCE_INDEXES:
        brow = board[sid]
        mrow = manifest[sid]
        verdict = brow["rf_verdict"]
        gated = 1 if verdict == GATE_VERDICT else 0

        # 板端 raw24_class 必须与 manifest 一致（fail-closed）。
        if int(brow["raw24_class"]) != int(mrow["raw24_class"]):
            errors.append("%d board raw24_class %s != manifest %s"
                          % (sid, brow["raw24_class"], mrow["raw24_class"]))

        sdir = os.path.join(failed_rx, str(sid))
        files_present = 0
        raw_sha_ok = -1  # -1=不适用(gated) / 0=错 / 1=对
        j = None
        if gated:
            # gated 样本不应有 failed_rx dump；若有则警告（可能是上一轮残留）。
            if os.path.isdir(sdir):
                errors.append("%d gated but has unexpected failed_rx dir" % sid)
            dump_json = {"source_index": sid}
        else:
            if not os.path.isdir(sdir):
                errors.append("%d rejected but missing failed_rx dir" % sid)
            else:
                missing = [f for f in REQUIRED_FILES
                           if not os.path.isfile(os.path.join(sdir, f))]
                files_present = len(REQUIRED_FILES) - len(missing)
                if missing:
                    errors.append("%d missing dump files: %s" % (sid, missing))
                jpath = os.path.join(sdir, "recovery_diagnostics.json")
                if os.path.isfile(jpath):
                    j = load_json_nan_tolerant(jpath)
                    for f in REQUIRED_JSON_FIELDS:
                        if f not in j:
                            errors.append("%d JSON missing field %s" % (sid, f))
                    if int(j.get("source_index", -1)) != sid:
                        errors.append("%d JSON source_index %s mismatch"
                                      % (sid, j.get("source_index")))
                raw_path = os.path.join(sdir, "raw_rx_ci16le.bin")
                sums_path = os.path.join(sdir, "SHA256SUMS.txt")
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
                        errors.append("%d raw_rx SHA mismatch actual=%s expected=%s"
                                      % (sid, actual, expected))
                else:
                    errors.append("%d raw_rx or SHA256SUMS missing" % sid)

        rows.append({
            "source_index": sid,
            "modulation": mrow["modulation"],
            "raw24_class": int(mrow["raw24_class"]),
            "gated": gated,
            "rf_verdict": verdict,
            "board_valid": brow["valid"],
            "board_raw24_pred": brow["raw24_pred"],
            "board_correct": brow["correct"],
            "training_residual": brow["training_residual"],
            "training_corr": brow["training_corr"],
            "raw_rx_sha256": (j or {}).get("raw_rx_sha256", ""),
            "raw_rx_sha_ok": raw_sha_ok,
            "files_present": files_present,
        })

    if errors:
        for e in errors:
            sys.stderr.write("ERROR: %s\n" % e)
        fail("inventory verification failed with %d error(s)" % len(errors))

    os.makedirs(out_dir, exist_ok=True)
    cols = ["source_index", "modulation", "raw24_class", "gated", "rf_verdict",
            "board_valid", "board_raw24_pred", "board_correct",
            "training_residual", "training_corr", "raw_rx_sha256",
            "raw_rx_sha_ok", "files_present"]
    out_path = os.path.join(out_dir, "inventory.tsv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in sorted(rows, key=lambda r: r["source_index"]):
            f.write("\t".join(str(r[c]) for c in cols) + "\n")

    n_gated = sum(r["gated"] for r in rows)
    n_rej = len(rows) - n_gated
    print("INVENTORY_OK samples=%d gated=%d rejected=%d out=%s"
          % (len(rows), n_gated, n_rej, out_path))
    return 0


# ----------------------------------------------------------------------------
# classify：读板端结果 + 导出 -> host BF16 -> 三套指标 + 5 交付物
# ----------------------------------------------------------------------------
def _resolve_sample(sid, brow, mrow, export_dir, capture_id, infer, collect_errors):
    """解析一个样本为逐样本 dict；rejected 时跑 forced classify 导出 + host BF16。"""
    source_class = int(mrow["raw24_class"])
    modulation = mrow["modulation"]
    verdict = brow["rf_verdict"]
    gated = 1 if verdict == GATE_VERDICT else 0

    base = {
        "source_index": sid,
        "source_class": source_class,
        "modulation": modulation,
        "rf_verdict": verdict,
        "gated": gated,
        "blocked_reason": None,
    }

    if gated:
        board_pred = int(brow["raw24_pred"])
        board_correct = int(brow["correct"])
        # gated 样本无 24 维 logits 导出（板端只出 argmax）。
        return {
            **base,
            "result_layer": BOARD_LAYER,
            "board_raw24_pred": board_pred,
            "baseline_pred": int(brow["baseline_pred"]),
            "board_label_correct": board_correct,
            "end_to_end_correct": 1 if board_correct == 1 else 0,
            "scalar_raw24_pred": board_pred,
            "scalar_label_correct": 1 if board_pred == source_class else 0,
            "wl_applicable": 0,
            "wl_raw24_pred": board_pred,
            "wl_label_correct": 1 if board_pred == source_class else 0,
            "forced_raw24_pred": board_pred,
            "forced_label_correct": 1 if board_pred == source_class else 0,
            "top1_logit": None,
            "top2_logit": None,
            "margin": None,
            "logit_finite": 1 if int(brow["valid"]) == 1 else 0,
            "training_residual": brow["training_residual"],
            "training_corr": brow["training_corr"],
            "payload_training_residual": "",
            "payload_training_corr": "",
            "raw_rx_sha256": "",
            "model_input_sha256": "",
        }

    # rejected：forced classify 导出目录 export_dir/<capture_id>/<sid>/
    idx_dir = os.path.join(export_dir, capture_id, str(sid))
    jpath = os.path.join(idx_dir, "forced_recovery.json")
    mi_path = os.path.join(idx_dir, "model_input_f32le.bin")
    if not os.path.isfile(jpath) or not os.path.isfile(mi_path):
        collect_errors.append("%d rejected but forced export missing (%s)" % (sid, idx_dir))
        base["blocked_reason"] = "forced_export_missing"
        return {**base, "result_layer": HOST_LAYER, "board_raw24_pred": -1,
                "baseline_pred": -1, "board_label_correct": -1,
                "end_to_end_correct": 0, "scalar_raw24_pred": -1,
                "scalar_label_correct": 0, "wl_applicable": 0,
                "wl_raw24_pred": -1, "wl_label_correct": 0,
                "forced_raw24_pred": -1, "forced_label_correct": 0,
                "top1_logit": None, "top2_logit": None, "margin": None,
                "logit_finite": 0, "training_residual": brow["training_residual"],
                "training_corr": brow["training_corr"],
                "payload_training_residual": "",
                "payload_training_corr": "", "raw_rx_sha256": "",
                "model_input_sha256": "",
                "_scalar_logits": None, "_wl_logits": None}

    j = load_json_nan_tolerant(jpath)
    if int(j.get("source_index", -1)) != sid:
        collect_errors.append("%d forced_recovery source_index %s mismatch"
                              % (sid, j.get("source_index")))
    if int(j.get("source_class", -1)) != source_class:
        collect_errors.append("%d forced_recovery source_class %s != manifest %d"
                              % (sid, j.get("source_class"), source_class))

    mi_bytes = open(mi_path, "rb").read()
    if len(mi_bytes) != MODEL_INPUT_BYTES:
        collect_errors.append("%d model_input size %d != %d"
                              % (sid, len(mi_bytes), MODEL_INPUT_BYTES))
        mi_arr = np.array([], dtype="<f4")
    else:
        mi_arr = np.frombuffer(mi_bytes, dtype="<f4")
    scalar_input_finite = bool(np.all(np.isfinite(mi_arr))) if mi_arr.size else False

    scalar_logits, scalar_pred, scalar_finite = infer(mi_path)
    wl_applicable = int(j.get("wide_linear", {}).get("applicable", 0))
    wl_pred = scalar_pred
    wl_logits = scalar_logits
    wl_finite = scalar_finite
    if wl_applicable:
        wl_mi = os.path.join(idx_dir, "wide_linear_model_input_f32le.bin")
        if not os.path.isfile(wl_mi):
            collect_errors.append("%d wide_linear_applicable but missing wl model_input" % sid)
        else:
            wl_logits, wl_pred, wl_finite = infer(wl_mi)

    wl_finite = wl_finite and int(j.get("wide_linear", {}).get("model_input_finite",
                                                              1 if wl_applicable else 0)) == 1
    model_input_finite = int(j.get("model_input_finite", 1 if scalar_input_finite else 0))
    logit_finite = 1 if (scalar_finite and wl_finite and scalar_input_finite
                         and model_input_finite == 1) else 0

    top1 = float(np.max(scalar_logits))
    srt = np.sort(scalar_logits)[::-1]
    top2 = float(srt[1]) if len(srt) > 1 else float("nan")
    margin = float(srt[0] - srt[1]) if len(srt) > 1 else float("nan")

    scalar_correct = 1 if scalar_pred == source_class else 0
    wl_correct = 1 if wl_pred == source_class else 0
    forced_pred = wl_pred if wl_applicable else scalar_pred
    forced_correct = wl_correct if wl_applicable else scalar_correct

    return {
        **base,
        "result_layer": HOST_LAYER,
        "board_raw24_pred": -1,
        "baseline_pred": -1,
        "board_label_correct": -1,
        "end_to_end_correct": 0,
        "scalar_raw24_pred": scalar_pred,
        "scalar_label_correct": scalar_correct,
        "wl_applicable": wl_applicable,
        "wl_raw24_pred": wl_pred,
        "wl_label_correct": wl_correct,
        "forced_raw24_pred": forced_pred,
        "forced_label_correct": forced_correct,
        "top1_logit": top1,
        "top2_logit": top2,
        "margin": margin,
        "logit_finite": logit_finite,
        "training_residual": brow["training_residual"],
        "training_corr": brow["training_corr"],
        "payload_training_residual": j.get("payload_training_residual", ""),
        "payload_training_corr": j.get("payload_training_corr", ""),
        "raw_rx_sha256": j.get("raw_rx_sha256", ""),
        "model_input_sha256": hashlib.sha256(mi_bytes).hexdigest() if mi_bytes else "",
        "_scalar_logits": scalar_logits,
        "_wl_logits": wl_logits,
    }


def phase_classify(args, infer=None):
    icraft_run = Path(args.icraft_run) if args.icraft_run else None
    model_dir = Path(args.model_dir) if args.model_dir else None
    captures_dir = args.captures_dir
    manifest_path = args.manifest
    export_dir = args.forced_classify_dir
    out_dir = args.out_dir or "results/full24_accuracy1"

    if not captures_dir or not os.path.isdir(captures_dir):
        fail("--captures-dir not found: %s" % captures_dir)
    if not export_dir or not os.path.isdir(export_dir):
        fail("--forced-classify-dir not found: %s" % export_dir)

    if infer is None:
        # 真实 host BF16 前向需要 icraft-run + 冻结模型。
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
        infer = lambda p: infer_one(icraft_run, model_json, model_raw, p)  # noqa: E731

    manifest = parse_manifest(manifest_path)
    board = parse_board_results(locate_board_results(captures_dir))
    capture_id = capture_id_of(captures_dir)

    errors = []
    samples = []
    for sid in EXPECT_SOURCE_INDEXES:
        s = _resolve_sample(sid, board[sid], manifest[sid], export_dir, capture_id,
                            infer, errors)
        samples.append(s)

    if errors:
        for e in errors:
            sys.stderr.write("ERROR: %s\n" % e)
        fail("classify verification failed with %d error(s)" % len(errors))

    samples.sort(key=lambda s: s["source_index"])
    metrics = compute_metrics(samples)
    _write_deliverables(samples, metrics, out_dir)

    m = metrics
    print("CLASSIFY_OK samples=%d end_to_end=%s scored=%d gated_correct=%s coverage=%.4f "
          "scalar_forced=%s wide_linear_forced=%s logit_finite=%s "
          "scalar_wl_disagree=%d conclusion=%s"
          % (m["sample_count"], m["end_to_end_correct"], m["scored"],
             m["gated_correct"], m["coverage"], m["scalar_forced_correct"],
             m["wide_linear_forced_correct"], m["logit_finite"],
             m["scalar_wide_linear_disagree"], m["conclusion"]))
    return 0


def _fmt(x):
    if x is None:
        return "NA"
    return "%.9g" % x


def _write_deliverables(samples, metrics, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    # ---- per_sample_results.tsv ----
    res_cols = ["source_index", "source_class", "modulation", "result_layer", "gated",
                "rf_verdict", "board_raw24_pred", "baseline_pred", "board_label_correct",
                "end_to_end_correct", "scalar_raw24_pred", "scalar_label_correct",
                "wl_applicable", "wl_raw24_pred", "wl_label_correct", "forced_raw24_pred",
                "forced_label_correct", "top1_logit", "top2_logit", "margin",
                "logit_finite", "training_corr", "training_residual",
                "payload_training_corr", "payload_training_residual",
                "raw_rx_sha256", "model_input_sha256"]
    with open(os.path.join(out_dir, "per_sample_results.tsv"), "w",
              encoding="utf-8", newline="") as f:
        f.write("\t".join(res_cols) + "\n")
        for r in samples:
            f.write("\t".join(
                str(r[c]) if c not in ("top1_logit", "top2_logit", "margin")
                else _fmt(r[c]) for c in res_cols) + "\n")

    # ---- raw24_logits.tsv ----
    logit_cols = ["source_index", "source_class", "modulation", "result_layer",
                  "variant"] + ["logit_%02d" % k for k in range(EXPECT_CLASS_COUNT)] + \
                 ["raw24_pred"]
    with open(os.path.join(out_dir, "raw24_logits.tsv"), "w",
              encoding="utf-8", newline="") as f:
        f.write("\t".join(logit_cols) + "\n")
        for r in samples:
            if r["gated"]:
                row = [r["source_index"], r["source_class"], r["modulation"],
                       r["result_layer"], "gated"] + \
                      ["NA"] * EXPECT_CLASS_COUNT + [r["board_raw24_pred"]]
                f.write("\t".join(str(x) for x in row) + "\n")
            else:
                # 有 24 维 logits 的只有 rejected（host BF16）。scalar 必写；
                # wide-linear 仅当 applicable 时另起一行。无 logits 的（blocked）写 NA。
                if r.get("_scalar_logits") is not None:
                    scalar = [r["source_index"], r["source_class"], r["modulation"],
                              r["result_layer"], "scalar"] + \
                             ["%.17g" % v for v in r["_scalar_logits"]] + \
                             [r["scalar_raw24_pred"]]
                else:
                    scalar = [r["source_index"], r["source_class"], r["modulation"],
                              r["result_layer"], "scalar"] + \
                             ["NA"] * EXPECT_CLASS_COUNT + [r["scalar_raw24_pred"]]
                f.write("\t".join(str(x) for x in scalar) + "\n")
                if r["wl_applicable"] and r.get("_wl_logits") is not None:
                    wl = [r["source_index"], r["source_class"], r["modulation"],
                          r["result_layer"], "wide_linear"] + \
                         ["%.17g" % v for v in r["_wl_logits"]] + \
                         [r["wl_raw24_pred"]]
                    f.write("\t".join(str(x) for x in wl) + "\n")

    # ---- confusion_24.csv（主 forced 答案，24×24 完整）----
    with open(os.path.join(out_dir, "confusion_24.csv"), "w", encoding="utf-8",
              newline="") as f:
        f.write("true\\pred," + ",".join(LABEL_ORDER_24) + "\n")
        for i in range(EXPECT_CLASS_COUNT):
            f.write(LABEL_ORDER_24[i] + "," + ",".join(str(metrics["confusion_24"][i])) + "\n")

    # ---- summary.json ----
    summary = {
        "task_id": "fix10class24-full24-accuracy1",
        "status": "M29-RML24-FIX10CLASS24-FULL24-ACCURACY1-AUDIT-COMPLETE",
        "baseline_full_sha256": BASELINE_FULL_SHA256,
        "result_layers": [BOARD_LAYER, HOST_LAYER],
        "production_gate_modified": 0,
        "production_threshold": 0.100,
        "decision_primary_variant": "wide_linear",
        "no_label_driven_variant_selection": 1,
        "metrics": {
            "end_to_end_correct": metrics["end_to_end_correct"],
            "end_to_end_accuracy": metrics["end_to_end_accuracy"],
            "scored": metrics["scored"],
            "gated_correct": metrics["gated_correct"],
            "coverage": metrics["coverage"],
            "gated_accuracy": metrics["gated_accuracy"],
            "scalar_forced_correct": metrics["scalar_forced_correct"],
            "wide_linear_forced_correct": metrics["wide_linear_forced_correct"],
            "forced_correct": metrics["forced_correct"],
            "logit_finite": metrics["logit_finite"],
            "scalar_wide_linear_disagree": metrics["scalar_wide_linear_disagree"],
        },
        "blocked": metrics["blocked"],
        "blocked_reasons": metrics["blocked_reasons"],
        "conclusion": metrics["conclusion"],
        "per_sample": [{
            "source_index": r["source_index"],
            "source_class": r["source_class"],
            "modulation": r["modulation"],
            "result_layer": r["result_layer"],
            "gated": r["gated"],
            "rf_verdict": r["rf_verdict"],
            "board_raw24_pred": r["board_raw24_pred"],
            "board_label_correct": r["board_label_correct"],
            "end_to_end_correct": r["end_to_end_correct"],
            "scalar_raw24_pred": r["scalar_raw24_pred"],
            "scalar_label_correct": r["scalar_label_correct"],
            "wl_applicable": r["wl_applicable"],
            "wl_raw24_pred": r["wl_raw24_pred"],
            "wl_label_correct": r["wl_label_correct"],
            "forced_raw24_pred": r["forced_raw24_pred"],
            "forced_label_correct": r["forced_label_correct"],
            "logit_finite": r["logit_finite"],
            "training_residual": r["training_residual"],
            "training_corr": r["training_corr"],
            "payload_training_residual": r["payload_training_residual"],
            "payload_training_corr": r["payload_training_corr"],
        } for r in samples],
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8", newline="") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="fix10class24-full24-accuracy1")
    ap.add_argument("--phase", required=True,
                    choices=["extract", "inventory", "classify"])
    ap.add_argument("--archive", help="rml24_full24_accuracy1 tar.gz path (extract)")
    ap.add_argument("--dest", help="fresh extraction destination dir (extract)")
    ap.add_argument("--captures-dir", help="board output dir (inventory/classify)")
    ap.add_argument("--manifest", help="clean24_smoke_manifest.tsv path (inventory/classify)")
    ap.add_argument("--out-dir", help="results dir (inventory/classify)")
    ap.add_argument("--forced-classify-dir", help="forced_classify_export dir (classify)")
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
        if not args.captures_dir or not args.manifest or not args.forced_classify_dir:
            ap.error("--phase classify requires --captures-dir, --manifest, --forced-classify-dir")
        return phase_classify(args)

    ap.error("unknown phase %s" % args.phase)


if __name__ == "__main__":
    sys.exit(main())
