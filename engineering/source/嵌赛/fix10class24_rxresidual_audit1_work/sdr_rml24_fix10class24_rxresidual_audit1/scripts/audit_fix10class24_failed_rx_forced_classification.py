#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix10class24-rxresidual-audit1 — 失败 RX 强制分类与残差归因审计（离线，不碰板）。

Phase A  `--phase extract`   归档 SHA 校验 + 安全解包（拒绝绝对路径/..穿越/符号链接/硬链接/越界）
         `--phase inventory` 30 样本身份校验 + 前端参数(run.log/summary.json)校验 + 产出 capture_inventory.tsv
Phase D  `--phase classify`  host BF16 强制分类（icraft-run.exe，≥2 前向）
Phase F  `--phase threshold` 门限敏感性（只读，标注选择偏差）

红线：不碰板 / 不改生产 0.100 门限 / 不改恢复器 / 不改模型 / 不改 canonical 资产 / 不改安全上限。
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
EXPECTED_ARCHIVE_SHA256 = (
    "08ef944e099270f5c166415df17eabed5c3324ff03a2940182318d4abef76922"
)

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

# run.log 里 RX_FRONTEND 行必须出现的字段
RX_FRONTEND_FIELDS = [
    "requested_rx_bw",
    "rx_bw_readback",
    "requested_rx_gain",
    "rx_gain_readback",
    "rx_bw_ok",
    "rx_gain_ok",
]

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


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
            continue  # 字符串字面量，不动
        p = re.sub(r'\bnan\b', 'NaN', p)
        p = re.sub(r'\binf\b', 'Infinity', p)
        p = re.sub(r'\b-inf\b', '-Infinity', p)
        parts[i] = p
    return "".join(parts)


def load_json_nan_tolerant(path):
    """读 JSON，容忍 nan/Infinity/-Infinity 字面量（板端 dump 含 snr_db=nan）。"""
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


def parse_kv_line(line):
    """把 `KEY k1=v1 k2=v2 ...` 解析成 dict。"""
    toks = line.strip().split()
    d = {}
    for t in toks[1:]:
        if "=" in t:
            k, v = t.split("=", 1)
            d[k] = v
    return d


def parse_bool(v):
    """把 '1'/'0'/'true'/'false'/True/False 归一化为 int 1/0。"""
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return 1 if v else 0
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return 1
    if s in ("0", "false", "no", "off"):
        return 0
    raise ValueError("not a bool: %r" % v)


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
    if got != EXPECTED_ARCHIVE_SHA256:
        fail("archive SHA mismatch: got %s expected %s" % (got, EXPECTED_ARCHIVE_SHA256))
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
            tf.extract(m, dest)  # extract into dest using member's own (safe) name
    tf.close()
    print("EXTRACT_OK archive_sha256=%s members=%d dest=%s" % (got, len(members), dest))
    return 0


# ----------------------------------------------------------------------------
# 前端参数解析
# ----------------------------------------------------------------------------
def parse_capture_id_dirname(dname):
    """返回 (encoded_variable, encoded_value, run_index) 或 None。"""
    m = re.match(r"^rml24_rxbw_(\d+)_run(\d+)_(\d+)$", dname)
    if m:
        return "rxbw", int(m.group(1)), int(m.group(2))
    m = re.match(r"^rml24_rxgain_(\d+)_run(\d+)_(\d+)$", dname)
    if m:
        return "rxgain", int(m.group(1)), int(m.group(2))
    return None


def frontend_from_run_log(log_path):
    """从 run.log 解析 FIX10CLASS24_BF16_RX_FRONTEND 行；找不到返回 None。"""
    if not os.path.isfile(log_path):
        return None
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "FIX10CLASS24_BF16_RX_FRONTEND" in line:
                d = parse_kv_line(line)
                missing = [k for k in RX_FRONTEND_FIELDS if k not in d]
                if missing:
                    fail("run.log RX_FRONTEND missing fields %s in %s" % (missing, log_path))
                out = {k: d[k] for k in RX_FRONTEND_FIELDS}
                return out
    return None


def frontend_from_summary(summary_path):
    """从 summary.json 解析前端字段；找不到返回 None。"""
    if not os.path.isfile(summary_path):
        return None
    d = load_json_nan_tolerant(summary_path)
    need = ["requested_rx_bw", "rx_bw_readback", "requested_rx_gain", "rx_gain_readback", "rx_bw_ok", "rx_gain_ok"]
    if any(k not in d for k in need):
        return None
    return {k: d[k] for k in need}


def nco_offset_evidence(log_path, summary_path):
    """确认无非零 --nco-offset。返回 (nco_offset, evidence)。"""
    # 优先查 run.log（含命令行），再查 summary.json
    if os.path.isfile(log_path):
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.search(r"--nco-offset[=\s]+(-?\d+(?:\.\d+)?)", line)
                if m:
                    val = float(m.group(1))
                    return val, "run_log_explicit"
        # run.log 无该字段 -> 生产缺省
        return 0.0, "production_default_and_board_command_omission"
    if os.path.isfile(summary_path):
        d = load_json_nan_tolerant(summary_path)
        if "nco_offset" in d:
            return float(d["nco_offset"]), "summary_json_explicit"
        return 0.0, "production_default_and_board_command_omission"
    return 0.0, "production_default_and_board_command_omission"


# ----------------------------------------------------------------------------
# inventory 主逻辑
# ----------------------------------------------------------------------------
def phase_inventory(captures_dir, out_dir):
    if not os.path.isdir(captures_dir):
        fail("captures dir not found: %s" % captures_dir)

    round_dirs = sorted(
        d for d in os.listdir(captures_dir)
        if os.path.isdir(os.path.join(captures_dir, d)) and parse_capture_id_dirname(d) is not None
    )
    if len(round_dirs) != 15:
        fail("expected 15 capture round dirs, got %d: %s" % (len(round_dirs), round_dirs))

    rows = []
    seen_keys = set()
    errors = []

    for dname in round_dirs:
        encoded_var, encoded_val, _run = parse_capture_id_dirname(dname)
        round_path = os.path.join(captures_dir, dname)
        log_path = os.path.join(round_path, "run.log")
        summary_path = os.path.join(round_path, "route_f_fix10class24_bf16_pc_tx_board_rx_summary.json")

        # 前端参数：rxbw 用 run.log，rxgain 用 summary.json
        fe = frontend_from_run_log(log_path)
        fe_source = "run.log"
        if fe is None:
            fe = frontend_from_summary(summary_path)
            fe_source = "summary.json"
        if fe is None:
            fail("no frontend params found for round %s" % dname)

        nco, nco_ev = nco_offset_evidence(log_path, summary_path)

        # 停止条件 #4：每个 capture_id 恰好含 source_index=500 与 1500 各一次（无多余/缺失）。
        fd = os.path.join(round_path, "failed_rx")
        if not os.path.isdir(fd):
            errors.append("%s missing failed_rx dir" % dname)
        else:
            actual = sorted(os.listdir(fd))
            if actual != ["1500", "500"]:
                errors.append("%s failed_rx source_index dirs %s != exactly [500, 1500]"
                              % (dname, actual))

        for source_index in ("1500", "500"):
            sdir = os.path.join(round_path, "failed_rx", source_index)
            key = (dname, source_index)
            if key in seen_keys:
                errors.append("duplicate primary key: %s" % (key,))
            seen_keys.add(key)

            if not os.path.isdir(sdir):
                errors.append("missing failed_rx dir: %s" % sdir)
                continue

            # 7 文件齐全
            missing_files = [f for f in REQUIRED_FILES if not os.path.isfile(os.path.join(sdir, f))]
            if missing_files:
                errors.append("%s/%s missing files: %s" % (dname, source_index, missing_files))

            jpath = os.path.join(sdir, "recovery_diagnostics.json")
            if not os.path.isfile(jpath):
                errors.append("%s/%s missing recovery_diagnostics.json" % (dname, source_index))
                continue
            j = load_json_nan_tolerant(jpath)
            missing_fields = [f for f in REQUIRED_JSON_FIELDS if f not in j]
            if missing_fields:
                errors.append("%s/%s JSON missing fields: %s" % (dname, source_index, missing_fields))

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
                    errors.append("%s/%s raw_rx SHA mismatch: actual=%s expected=%s"
                                  % (dname, source_index, actual, expected))
            else:
                errors.append("%s/%s raw_rx or SHA256SUMS missing" % (dname, source_index))

            # 前端一致：只核对目录名实际编码的变量
            if encoded_var == "rxbw":
                encoded_match = 1 if int(fe["requested_rx_bw"]) == encoded_val else 0
            else:  # rxgain
                encoded_match = 1 if int(float(fe["requested_rx_gain"])) == encoded_val else 0
            if encoded_match != 1:
                errors.append("%s dir-encoded %s=%d != requested %s" %
                              (dname, encoded_var, encoded_val, fe.get("requested_rx_bw") if encoded_var == "rxbw" else fe.get("requested_rx_gain")))

            rx_bw_ok = parse_bool(fe["rx_bw_ok"])
            rx_gain_ok = parse_bool(fe["rx_gain_ok"])
            if rx_bw_ok != 1:
                errors.append("%s rx_bw_ok=%s (expected 1)" % (dname, fe["rx_bw_ok"]))
            if rx_gain_ok != 1:
                errors.append("%s rx_gain_ok=%s (expected 1)" % (dname, fe["rx_gain_ok"]))

            rows.append({
                "capture_id": dname,
                "source_index": source_index,
                "modulation": j.get("modulation", ""),
                "raw24_class": j.get("raw24_class", ""),
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
                "requested_rx_bw": fe["requested_rx_bw"],
                "rx_bw_readback": fe["rx_bw_readback"],
                "rx_bw_ok": rx_bw_ok,
                "requested_rx_gain": fe["requested_rx_gain"],
                "rx_gain_readback": fe["rx_gain_readback"],
                "rx_gain_ok": rx_gain_ok,
                "dir_encoded_variable": encoded_var,
                "dir_encoded_value": encoded_val,
                "encoded_match": encoded_match,
                "nco_offset": nco,
                "nco_offset_evidence": nco_ev,
                "raw_rx_sha_ok": raw_sha_ok,
                "files_present": "%d/%d" % (len(REQUIRED_FILES) - len(missing_files), len(REQUIRED_FILES)),
                "frontend_source": fe_source,
            })

    if errors:
        for e in errors:
            sys.stderr.write("ERROR: %s\n" % e)
        fail("inventory verification failed with %d error(s)" % len(errors))

    # 停止条件复核
    n_capture_ids = len(set(r["capture_id"] for r in rows))
    n_keys = len(rows)
    if n_capture_ids != 15 or n_keys != 30:
        fail("stop condition unmet: capture_ids=%d keys=%d (want 15/30)" % (n_capture_ids, n_keys))
    for dname in round_dirs:
        idxs = sorted(int(r["source_index"]) for r in rows if r["capture_id"] == dname)
        if idxs != [500, 1500]:
            fail("capture %s source_index set %s != [500, 1500]" % (dname, idxs))

    os.makedirs(out_dir, exist_ok=True)
    cols = ["capture_id", "source_index", "modulation", "raw24_class", "failure", "failure_enum",
            "payload_training_residual", "payload_training_corr", "timing_offset", "coarse_cfo_hz",
            "fine_cfo_hz", "target_rms", "tx_scale", "raw_rx_sha256",
            "requested_rx_bw", "rx_bw_readback", "rx_bw_ok", "requested_rx_gain", "rx_gain_readback",
            "rx_gain_ok", "dir_encoded_variable", "dir_encoded_value", "encoded_match",
            "nco_offset", "nco_offset_evidence", "raw_rx_sha_ok", "files_present", "frontend_source"]
    out_path = os.path.join(out_dir, "capture_inventory.tsv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in sorted(rows, key=lambda r: (r["capture_id"], int(r["source_index"]))):
            f.write("\t".join(str(r[c]) for c in cols) + "\n")

    print("CAPTURE_INVENTORY_OK capture_ids=%d samples=%d out=%s" % (n_capture_ids, n_keys, out_path))
    return 0


# ----------------------------------------------------------------------------
# Phase D / Phase F 常量与工具
# ----------------------------------------------------------------------------
NETWORK_NAME = "model_24class"
EXPECT_CLASS_COUNT = 24
HOST_LAYER = "HOST_BF16_FORCED_CLASSIFICATION"   # 非板端 NPU 实测

# 冻结 BF16 24 类模型身份（fail-closed：误跑错模型直接拒绝）
FROZEN_MODEL_JSON_SHA256 = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA256 = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

CANDIDATE_THRESHOLDS = [0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16]


def read_tsv(path):
    """读 TSV，返回 (header, rows)。rows 是 dict 列表（按 header 键）。"""
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
    """对单个 model_input 跑 ≥2 前向，返回逐 pass 结果字典。"""
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


# ----------------------------------------------------------------------------
# Phase D -- host BF16 强制分类
# ----------------------------------------------------------------------------
def phase_classify(args):
    icraft_run = Path(args.icraft_run) if args.icraft_run else None
    model_dir = Path(args.model_dir) if args.model_dir else None
    forced_dir = args.forced_classify_dir
    baseline_path = args.baseline
    out_dir = args.out_dir or "results/rxresidual_audit"

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

    # 冻结 BF16 baseline：source_index -> frozen_bf16_raw24_pred
    if not baseline_path or not os.path.isfile(baseline_path):
        fail("--baseline not found")
    _, b_rows = read_tsv(baseline_path)
    baseline_pred = {}
    for r in b_rows:
        baseline_pred[int(r["source_index"])] = int(r["frozen_bf16_raw24_pred"])

    # 收集 30 个导出目录（主键 capture_id + source_index）
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

    if len(samples) != 30:
        fail("expected 30 exported samples, got %d" % len(samples))
    keys = set()
    for cap, idx, _, _, _ in samples:
        k = (cap, idx)
        if k in keys:
            fail("duplicate export key: %s" % (k,))
        keys.add(k)

    logit_rows = []
    result_rows = []
    for cap, idx, idx_path, mi, j in sorted(samples, key=lambda s: (s[0], s[1])):
        # model input 校验：8192 字节 / 2048 fp32
        mi_bytes = open(mi, "rb").read()
        if len(mi_bytes) != 8192:
            fail("model_input_f32le.bin size %d != 8192: %s" % (len(mi_bytes), mi))
        mi_arr = np.frombuffer(mi_bytes, dtype="<f4")
        input_finite = bool(np.all(np.isfinite(mi_arr)))

        passes = classify_one_sample(icraft_run, model_json, model_raw, Path(mi), n_passes=2)

        sc = int(j["source_class"])
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

        # raw24_logits.tsv：pass-1 的 24 个 logits
        logit_rows.append({
            "capture_id": cap,
            "source_index": idx,
            "source_class": sc,
            **{"logit_%02d" % k: ("%.17g" % p1["logits"][k]) for k in range(EXPECT_CLASS_COUNT)},
            "raw24_pred_pass1": pred1,
            "raw24_pred_pass2": pred2,
        })

        result_rows.append({
            "capture_id": cap,
            "source_index": idx,
            "source_class": sc,
            "baseline_pred": bpred,
            "label": sc,
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

    logit_cols = ["capture_id", "source_index", "source_class"] + \
                 ["logit_%02d" % k for k in range(EXPECT_CLASS_COUNT)] + \
                 ["raw24_pred_pass1", "raw24_pred_pass2"]
    with open(os.path.join(out_dir, "raw24_logits.tsv"), "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(logit_cols) + "\n")
        for r in sorted(logit_rows, key=lambda r: (r["capture_id"], r["source_index"])):
            f.write("\t".join(str(r[c]) for c in logit_cols) + "\n")

    res_cols = ["capture_id", "source_index", "source_class", "baseline_pred", "label",
                "raw24_pred_pass1", "raw24_pred_pass2", "baseline_agreement", "label_correct",
                "finite", "repeat_argmax_deterministic", "repeat_logits_byte_identical",
                "top1_logit", "top2_logit", "margin", "payload_training_residual",
                "payload_training_corr", "raw_rx_sha256", "model_input_sha256", "result_layer"]
    with open(os.path.join(out_dir, "per_capture_results.tsv"), "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(res_cols) + "\n")
        for r in sorted(result_rows, key=lambda r: (r["capture_id"], r["source_index"])):
            f.write("\t".join(str(r[c]) for c in res_cols) + "\n")

    n = len(result_rows)
    print("CLASSIFY_OK samples=%d baseline_agreement=%d/%d label_correct=%d/%d "
          "finite=%d/%d repeat_argmax=%d/%d repeat_logits_byte=%d/%d layer=%s" %
          (n,
           sum(r["baseline_agreement"] for r in result_rows), n,
           sum(r["label_correct"] for r in result_rows), n,
           sum(r["finite"] for r in result_rows), n,
           sum(r["repeat_argmax_deterministic"] for r in result_rows), n,
           sum(r["repeat_logits_byte_identical"] for r in result_rows), n,
           HOST_LAYER))
    return 0


# ----------------------------------------------------------------------------
# Phase F -- 门限敏感性（只读 + 标注选择偏差）
# ----------------------------------------------------------------------------
def phase_threshold(args):
    out_dir = args.out_dir or "results/rxresidual_audit"
    results_path = os.path.join(out_dir, "per_capture_results.tsv")
    if not os.path.isfile(results_path):
        fail("per_capture_results.tsv not found; run --phase classify first")
    _, res_rows = read_tsv(results_path)

    rows = []
    for T in CANDIDATE_THRESHOLDS:
        admitted = [r for r in res_rows
                    if float(r["payload_training_residual"]) <= T]
        n = len(admitted)
        n_agree = sum(int(r["baseline_agreement"]) for r in admitted)
        n_correct = sum(int(r["label_correct"]) for r in admitted)
        n_finite = sum(int(r["finite"]) for r in admitted)
        n_bpsk = sum(1 for r in admitted if int(r["source_class"]) == 3)
        n_4ask = sum(1 for r in admitted if int(r["source_class"]) == 1)
        n_misadmit = sum(1 for r in admitted if int(r["label_correct"]) == 0)
        rows.append({
            "threshold": "%.2f" % T,
            "admitted_samples": n,
            "baseline_agreement": "%d/%d" % (n_agree, n),
            "label_accuracy": "%.4f" % (n_correct / n) if n else "n/a",
            "BPSK_admitted": n_bpsk,
            "4ASK_admitted": n_4ask,
            "finite_rate": "%.4f" % (n_finite / n) if n else "n/a",
            "mis_admitted_errors": n_misadmit,
        })

    os.makedirs(out_dir, exist_ok=True)
    cols = ["threshold", "admitted_samples", "baseline_agreement", "label_accuracy",
            "BPSK_admitted", "4ASK_admitted", "finite_rate", "mis_admitted_errors"]
    out_path = os.path.join(out_dir, "threshold_sensitivity.tsv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]) for c in cols) + "\n")

    # 选择偏差声明：这 30 个样本全是 0.100 拒绝后的失败样本，不是全体 RF 样本。
    print("THRESHOLD_SENSITIVITY_OK selection_bias=FAILURE_CONDITIONAL_SAMPLE "
          "baseline_0100_unchanged=1 conclusion=EVIDENCE_SUPPORTS_A_PROSPECTIVE_"
          "THRESHOLD_VALIDATION out=%s" % out_path)
    print("NOTE: 30 samples are all failure-condition samples rejected by 0.100; "
          "do NOT recommend a global production threshold from this set.")
    return 0



# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="fix10class24-rxresidual-audit1")
    ap.add_argument("--phase", required=True, choices=["extract", "inventory", "classify", "threshold"])
    ap.add_argument("--archive", help="rml24_rx_diagnostics_full tar.gz path")
    ap.add_argument("--captures-dir", help="extracted captures root (for inventory)")
    ap.add_argument("--out-dir", help="results output dir (default results/rxresidual_audit)")
    ap.add_argument("--dest", help="extraction destination (for extract)")
    ap.add_argument("--icraft-run", help="path to icraft-run.exe (for classify)")
    ap.add_argument("--model-dir", help="BF16 model dir with rml24_adamrv11_bf16.json/.raw (for classify)")
    ap.add_argument("--forced-classify-dir", help="forced_classify_export root (for classify)")
    ap.add_argument("--baseline", help="clean24_smoke_raw24_bf16_baseline.tsv (for classify)")
    args = ap.parse_args()

    if args.phase == "extract":
        if not args.archive or not args.dest:
            fail("--phase extract requires --archive and --dest")
        return phase_extract(args.archive, args.dest)

    out_dir = args.out_dir or "results/rxresidual_audit"

    if args.phase == "inventory":
        if not args.captures_dir:
            fail("--phase inventory requires --captures-dir")
        return phase_inventory(args.captures_dir, out_dir)
    if args.phase == "classify":
        return phase_classify(args)
    if args.phase == "threshold":
        return phase_threshold(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
