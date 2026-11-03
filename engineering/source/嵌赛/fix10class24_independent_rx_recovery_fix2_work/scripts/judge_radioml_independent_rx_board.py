#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""judge_radioml_independent_rx_board.py -- fix1v2 board impl1 板端独立接收判读器。

读板端 runner 实际产出的 **23 列** `board_independent_rx_results.tsv` + 运行级
`board_independent_rx_summary.tsv`，与冻结的公共协议 manifest 对齐，输出**承诺的独立对照
统计**（纯离线、只读判定；不碰板/不发射/不训练/不归因 RF）。

这解决了复查第 5 项的 3 个缺口：
  1. **读取数字基线**（`--digital-baseline` 指向 host 数字重放 `independent_rx_replay.tsv`，
     19 列，`recovered_pred` 为 host 恢复预测），计算 **预测一致率 / 同错 / 新增翻转**。
  2. **核验板端实际张量文件**（`--tensor-dir` 指向板端 `$OUT` 目录，逐文件读
     `<sid>.recovered.tensor.bin` 算 SHA，与 TSV 声明的 `model_input_sha256` 比对），
     发现文件缺失/被篡改，而非只信 TSV 里的 SHA。
  3. **重复 ID 在加载期即检测并报错**（不再被 dict 静默覆盖）；并**明确区分**
     「分析执行成功」与「本轮测量完整有效」——前者是判读器自身能否跑完，后者是测量本身
     是否完整有效，二者用不同的退出码区分。

第 4 轮复查追加两处判读修复（S1/S2，不再改恢复算法/模型/波形）：
  - **S1 一致率分母**：主指标 `agreement_over_expected` = 有效一致预测数 / 24（分母恒为
    24），条件一致率 `conditional_agreement` = 有效一致预测数 / 有效行数（另列）。缺行/
    门拒/非有限/未捕获/未分类(-1)行**不**计入分子，分别计 `n_missing/n_rejected/n_invalid`
    报告；同错/新增翻转/板端纠正只在有效行上算。correct/24、coverage、gated accuracy、
    end-to-end accuracy 各自独立输出。
  - **S2 数字基线身份绑定**：`--baseline-identity <sidecar.json>`（与 `--digital-baseline`
    联用）把数字基线绑定到其确切的 (source_id, conversion_version, TX manifest SHA, 数字
    基线 replay TSV SHA, 冻结 BF16 模型 json/raw SHA)。manifest/数字基线 SHA 不符、或模型
    身份不符 → 分析失败（rc=1）；文件模式另把数字基线每源 B 张量 SHA 绑定到 `--layers-dir`
    同名 bin。设备模式不比较 RF C 张量与 B 层字节。

输入（--kind 二选一，与板端 --capture-source 对应）：
    --kind file
        --results    <OUT>/board_independent_rx_results.tsv   （23 列）
        --summary    <OUT>/board_independent_rx_summary.tsv   （22 列）
        --manifest   <tx_package>/public_protocol_tx_manifest.tsv（10 列）
        --layers-dir <replay_out>/layers                        （数字 B 层参考 bin）
        --tensor-dir <OUT>                                      （板端实际张量文件目录）
        --digital-baseline <replay_out>/independent_rx_replay.tsv（数字基线，19 列）
        --out-json   <out>.json
        判据：每个 <sid>.recovered.tensor.bin 的 SHA 必须与数字 B 层参考逐字节相同、
        板端实际张量文件必须存在且 SHA 与 TSV 声明一致、board_pred 与数字基线 recovered_pred
        24/24 一致（无新增翻转）。

    --kind device
        --results / --summary / --manifest / --tensor-dir / --out-json
        （--layers-dir 不适用；--digital-baseline 可选，提供时计算预测一致率/同错/新增翻转，
        仅作记录不做 RF 归因）
        判据：如实记录 completed / n_gated / n_classified / n_correct(board_pred==class_index)
        / gate_reject / hard_invalid / no_sync / rx_clipped / capture_ok 与
        training_residual_rel <= 0.100 门；**不做 RF 归因**。

退出码（fail-closed，三态）：
    0 = 分析执行成功 且 本轮测量完整有效
    1 = 分析执行失败（输入缺失/表头错/列数错/重复 ID/身份不一致 → 无法产生可信判定）
    2 = 分析执行成功，但本轮测量不完整或无效（缺源/摘要漂移/字节不符/张量文件缺失或篡改/
        文件模式预测不一致/ completed!=1 或 functional_pass!=1）

Usage:
    python -I scripts/judge_radioml_independent_rx_board.py --kind file \
        --results <OUT>/board_independent_rx_results.tsv \
        --summary <OUT>/board_independent_rx_summary.tsv \
        --manifest <tx>/public_protocol_tx_manifest.tsv \
        --layers-dir <replay>/layers --tensor-dir <OUT> \
        --digital-baseline <replay>/independent_rx_replay.tsv \
        --baseline-identity scripts/digital_baseline_identity.json --out-json <out>.json
    python -I scripts/judge_radioml_independent_rx_board.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

TOKEN = "M29-RML24-FIX10CLASS24-INDEPENDENT-RX-BOARD-IMPL1-JUDGER"
K_GATE = 0.100        # frozen production gate (training_residual_rel, gain-independent)
K_SOURCES = 24

# 冻结 BF16 模型身份（板端 NPU 推理只用 json+raw；ckpt 是 host 训练产物不上板）。
# 数字基线身份 sidecar 声明的模型 SHA 必须与此一致（防篡改/防换模型）。
FROZEN_MODEL_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

RESULT_HEADER = ("source_index\tclass_index\tclass_name\ttiming_offset\tcoarse_cfo_hz\t"
                 "fractional_timing\tcfo_preamble_legacy_hz\t"
                 "a_real\ta_imag\tb_real\tb_imag\ttraining_residual\ttraining_residual_rel\t"
                 "gated\tfinite\trepeatable\tboard_pred\tcapture_ok\tno_sync\trx_clipped\t"
                 "raw_rx_sha256\tlogits_sha256\tmodel_input_sha256")

SUMMARY_HEADER = ("sources\tprocessed\tgated\tgate_reject\thard_invalid\tno_sync\t"
                  "rx_clipped\tclassified\tcorrect\tcompleted\taborted\taborted_reason\t"
                  "restore_ok\ttx_restore_ok\trx_readback_ok\tnegative_control_pass\t"
                  "noise_rms\tnoise_sync_score\tfunctional_pass\tsource_id\tversion\t"
                  "capture_source")

MANIFEST_HEADER = ("source_id\tconversion_version\tsource_index\tclass_index\tclass_name\t"
                   "seed\tburst_file\tburst_sha256\tpayload_ci16_sha256\tmodel_input_sha256")

# host 数字重放基线（19 列），recovered_pred(6) 是 host 对恢复后 B 层张量的预测，
# model_input_sha256(19) 必须与 --layers-dir 下同名 bin 的 SHA 一致（同一 host 重放）。
DIGITAL_HEADER = ("source_index\tclass_index\tclass_name\torig_pred\torig_correct\t"
                  "recovered_pred\trecovered_correct\trotated_pred\trotated_correct\tfinite\t"
                  "orig_rms\torig_dc_real\torig_dc_imag\trecovered_rms\trecovered_dc_real\t"
                  "recovered_dc_imag\tcorr_orig_recovered\tresid_orig_recovered\t"
                  "model_input_sha256")

TENSOR_SUFFIX = ".recovered.tensor.bin"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _fmt(x):
    return "n/a" if x is None else "%.6f" % x


def read_lines(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("empty file: %s" % path)
    return lines


def _check_header(lines, expected, what):
    got = lines[0].rstrip("\n")
    if got != expected:
        raise ValueError("%s header mismatch (got %d cols %r)" %
                         (what, len(got.split("\t")), got))


def load_manifest(manifest: Path):
    lines = read_lines(manifest)
    _check_header(lines, MANIFEST_HEADER, "manifest")
    rows = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != 10:
            raise ValueError("manifest row has %d cols (want 10): %s" % (len(f), ln))
        sid = int(f[2])
        if sid in rows:
            raise ValueError("manifest duplicate source_index=%d" % sid)
        rows[sid] = {
            "source_id": f[0], "conversion_version": f[1],
            "source_index": sid, "class_index": int(f[3]), "class_name": f[4],
            "burst_file": f[6], "burst_sha256": f[7],
            "model_input_sha256": f[9],
        }
    if len(rows) != K_SOURCES:
        raise ValueError("manifest has %d rows (want %d)" % (len(rows), K_SOURCES))
    return rows


def load_results(path: Path):
    lines = read_lines(path)
    _check_header(lines, RESULT_HEADER, "results")
    rows = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != 23:
            raise ValueError("results row has %d cols (want 23): %s" % (len(f), ln))
        sid = int(f[0])
        if sid in rows:
            raise ValueError("results duplicate source_index=%d" % sid)
        rows[sid] = {
            "source_index": sid, "class_index": int(f[1]), "class_name": f[2],
            "timing_offset": int(f[3]), "coarse_cfo_hz": float(f[4]),
            "fractional_timing": float(f[5]),
            "cfo_preamble_legacy_hz": float(f[6]),
            "training_residual": float(f[11]), "training_residual_rel": float(f[12]),
            "gated": int(f[13]), "finite": int(f[14]), "repeatable": int(f[15]),
            "board_pred": int(f[16]), "capture_ok": int(f[17]), "no_sync": int(f[18]),
            "rx_clipped": int(f[19]), "raw_rx_sha256": f[20], "logits_sha256": f[21],
            "model_input_sha256": f[22],
        }
    return rows


def load_summary(path: Path):
    lines = read_lines(path)
    _check_header(lines, SUMMARY_HEADER, "summary")
    data = [ln for ln in lines[1:] if ln.strip()]
    if len(data) != 1:
        raise ValueError("summary has %d data rows (want 1)" % len(data))
    f = data[0].split("\t")
    if len(f) != 22:
        raise ValueError("summary row has %d cols (want 22)" % len(f))
    return {
        "sources": int(f[0]), "processed": int(f[1]), "gated": int(f[2]),
        "gate_reject": int(f[3]), "hard_invalid": int(f[4]), "no_sync": int(f[5]),
        "rx_clipped": int(f[6]), "classified": int(f[7]), "correct": int(f[8]),
        "completed": int(f[9]), "aborted": int(f[10]), "aborted_reason": f[11],
        "restore_ok": int(f[12]), "tx_restore_ok": int(f[13]),
        "rx_readback_ok": int(f[14]), "negative_control_pass": int(f[15]),
        "noise_rms": float(f[16]), "noise_sync_score": float(f[17]),
        "functional_pass": int(f[18]), "source_id": f[19], "version": f[20],
        "capture_source": f[21],
    }


def load_digital_baseline(path: Path):
    lines = read_lines(path)
    _check_header(lines, DIGITAL_HEADER, "digital baseline")
    rows = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != 19:
            raise ValueError("digital baseline row has %d cols (want 19): %s" %
                             (len(f), ln))
        sid = int(f[0])
        if sid in rows:
            raise ValueError("digital baseline duplicate source_index=%d" % sid)
        rows[sid] = {
            "source_index": sid, "class_index": int(f[1]), "class_name": f[2],
            "recovered_pred": int(f[5]), "recovered_correct": int(f[6]),
            "model_input_sha256": f[18],
        }
    if len(rows) != K_SOURCES:
        raise ValueError("digital baseline has %d rows (want %d)" % (len(rows), K_SOURCES))
    return rows


def recompute_stats(rows, manifest):
    """从 23 列结果**独立重算**可直接观察的运行级统计（不信任 summary）。

    只重算行内可观察的量：processed/gated/classified/correct/no_sync/rx_clipped/capture_fail。
    gate_reject 与 hard_invalid 依赖 runner 内部的 finite_est / invertible 状态
    （奇异逆 / 病态逆不会在行内暴露），故**不重算**，只沿用 summary 的权威计数，
    避免因病态逆边界产生假漂移。
    """
    st = {
        "n_processed": len(rows), "n_gated": 0,
        "n_classified": 0, "n_correct": 0,
        "n_no_sync": 0, "n_rx_clipped": 0, "n_capture_fail": 0,
    }
    for r in rows.values():
        ci = manifest[r["source_index"]]["class_index"]
        if r["gated"] == 1:
            st["n_gated"] += 1
            if r["finite"] == 1:
                st["n_classified"] += 1
                if r["board_pred"] == ci:
                    st["n_correct"] += 1
        if r["no_sync"] == 1:
            st["n_no_sync"] += 1
        if r["rx_clipped"] == 1:
            st["n_rx_clipped"] += 1
        if r["capture_ok"] == 0:
            st["n_capture_fail"] += 1
    return st


def validate_identity(rows, manifest):
    """身份一致性（分析级）：results 里每个 source_index 必须存在于 manifest 且 class 一致。
    返回 (identity_errors, missing)：
      - identity_errors：results 声明了 manifest 没有的源 / class 与 manifest 不符（分析级）。
      - missing：manifest 有但 results 缺失的源（测量不完整级）。
    """
    identity_errors, missing = [], []
    for sid in sorted(rows):
        m = manifest.get(sid)
        if m is None:
            identity_errors.append("IDENTITY source_index=%d not in manifest" % sid)
            continue
        r = rows[sid]
        if r["class_index"] != m["class_index"]:
            identity_errors.append("IDENTITY_MISMATCH source_index=%d class %d != manifest %d"
                                   % (sid, r["class_index"], m["class_index"]))
        if r["class_name"] != m["class_name"]:
            identity_errors.append("CLASS_NAME_MISMATCH source_index=%d %r != manifest %r"
                                   % (sid, r["class_name"], m["class_name"]))
    missing = sorted(set(manifest) - set(rows))
    return identity_errors, missing


def verify_file_byte_identical(rows, layers_dir):
    """文件模式独立对照：板端 recovered tensor SHA（TSV 声明）== 数字 B 层参考 bin SHA。"""
    ok, bad = 0, []
    for sid in sorted(rows):
        if layers_dir is None:
            bad.append("source_index=%d no --layers-dir to verify" % sid)
            continue
        f = layers_dir / ("%d%s" % (sid, TENSOR_SUFFIX))
        if not f.is_file():
            bad.append("source_index=%d digital B-layer bin missing: %s" % (sid, f))
            continue
        ref = sha256_bytes(f.read_bytes())
        got = rows[sid]["model_input_sha256"]
        if ref != got:
            bad.append("source_index=%d byte-identical FAIL (B-layer %s... board %s...)"
                       % (sid, ref[:16], got[:16]))
        else:
            ok += 1
    return ok, bad


def verify_board_tensor_files(rows, tensor_dir):
    """核验板端**实际**张量文件（缺口 2）：读 <tensor_dir>/<sid>.recovered.tensor.bin 算 SHA，
    与 TSV 声明的 model_input_sha256 逐字节比对，发现文件缺失或被篡改。"""
    ok, bad = 0, []
    for sid in sorted(rows):
        if tensor_dir is None:
            bad.append("source_index=%d no --tensor-dir to verify" % sid)
            continue
        f = tensor_dir / ("%d%s" % (sid, TENSOR_SUFFIX))
        if not f.is_file():
            bad.append("source_index=%d board tensor file missing: %s" % (sid, f))
            continue
        actual = sha256_bytes(f.read_bytes())
        declared = rows[sid]["model_input_sha256"]
        if actual != declared:
            bad.append("source_index=%d board tensor SHA mismatch (file %s... declared %s...)"
                       % (sid, actual[:16], declared[:16]))
        else:
            ok += 1
    return ok, bad


def load_baseline_identity(path: Path):
    """读冻结数字基线身份 sidecar（S2）：映射 (source_id, conversion_version) →
    该基线的确切 TX manifest SHA + 数字基线 replay TSV SHA，并声明冻结模型身份。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "model" not in data or "baselines" not in data:
        raise ValueError("baseline-identity missing 'model' or 'baselines'")
    model = data["model"]
    if not isinstance(model, dict) or "json_sha256" not in model or "raw_sha256" not in model:
        raise ValueError("baseline-identity 'model' missing json_sha256/raw_sha256")
    if not isinstance(data["baselines"], dict) or not data["baselines"]:
        raise ValueError("baseline-identity 'baselines' empty or not a dict")
    return data


def bind_baseline(manifest, manifest_path, digital_path, sidecar):
    """把当前 --manifest + --digital-baseline 绑定到 sidecar 里的冻结身份（S2）。

    返回 (entry, errors)：
      - entry：命中的 (source_id/version) 记录（含 manifest_sha256/baseline_tsv_sha256），
        或 None（未命中）。
      - errors：分析级身份错误（BASELINE_UNBOUND / BASELINE_MANIFEST_SHA_MISMATCH /
        BASELINE_TSV_SHA_MISMATCH / BASELINE_MODEL_IDENTITY_MISMATCH）。
    目的：正确 v2 manifest/summary + 误选的 v1 数字基线，其 baseline_tsv_sha256 不符，
    会被显式拒绝（而不是被当成 RF 新增翻转）。"""
    errors = []
    model = sidecar["model"]
    if model.get("json_sha256") != FROZEN_MODEL_JSON_SHA:
        errors.append("BASELINE_MODEL_IDENTITY_MISMATCH json_sha256=%s"
                      % model.get("json_sha256"))
    if model.get("raw_sha256") != FROZEN_MODEL_RAW_SHA:
        errors.append("BASELINE_MODEL_IDENTITY_MISMATCH raw_sha256=%s"
                      % model.get("raw_sha256"))

    sid0 = min(manifest)
    source_id = manifest[sid0]["source_id"]
    version = manifest[sid0]["conversion_version"]
    key = "%s/%s" % (source_id, version)
    entry = sidecar["baselines"].get(key)
    if entry is None:
        errors.append("BASELINE_UNBOUND no identity record for %s (known: %s)"
                      % (key, sorted(sidecar["baselines"])))
        return None, errors
    msha = sha256_bytes(Path(manifest_path).read_bytes())
    if msha != entry.get("manifest_sha256"):
        errors.append("BASELINE_MANIFEST_SHA_MISMATCH %s file=%s declared=%s"
                      % (key, msha[:16], (entry.get("manifest_sha256") or "")[:16]))
    if digital_path is not None:
        dsha = sha256_bytes(Path(digital_path).read_bytes())
        if dsha != entry.get("baseline_tsv_sha256"):
            errors.append("BASELINE_TSV_SHA_MISMATCH %s file=%s declared=%s"
                          % (key, dsha[:16], (entry.get("baseline_tsv_sha256") or "")[:16]))
    return entry, errors


def verify_digital_baseline_binding(manifest, digital, layers_dir):
    """文件模式（S2）：数字基线每源 model_input_sha256（host 恢复 B 层）== --layers-dir
    同名 bin 的 SHA，把数字基线的 B 张量 SHA 记录绑定到参考工件，防 --layers-dir 与
    --digital-baseline 指向不同 host 重放（v1/v2 混用）。仅文件模式做；设备模式不比较
    RF C 张量与 B 层字节。"""
    ok, bad = 0, []
    for sid in sorted(manifest):
        f = layers_dir / ("%d%s" % (sid, TENSOR_SUFFIX))
        if not f.is_file():
            bad.append("source_index=%d layers bin missing: %s" % (sid, f))
            continue
        ref = sha256_bytes(f.read_bytes())
        if ref != digital[sid]["model_input_sha256"]:
            bad.append("source_index=%d digital baseline B SHA != layers bin (%s vs %s)"
                       % (sid, digital[sid]["model_input_sha256"][:16], ref[:16]))
        else:
            ok += 1
    return ok, bad


def _is_valid_classification(r):
    """一行是否算「有效可分类」：过门、有限、捕获成功、无失同步、未削波，且确有预测
    （board_pred 是 0..23 的真实类别，不是 -1 门拒/未分类）。缺行/门拒/非有限/未捕获
    都**不算**有效分类，不进入一致率/正确率的分子（留在 expected=24 分母里）。"""
    return (r["gated"] == 1 and r["finite"] == 1 and r["capture_ok"] == 1 and
            r["no_sync"] == 0 and r["rx_clipped"] == 0 and r["board_pred"] >= 0)


def compute_classification(rows, manifest):
    """分类统计（S1 修复）：主指标分母恒为 expected=24，缺行/门拒/无效行**不**计入分子，
    且分别计数报告。correct/24、coverage、gated accuracy、end-to-end accuracy 各自独立。"""
    expected = K_SOURCES
    n_valid = n_rejected = n_invalid = n_correct = n_missing = 0
    for sid in sorted(manifest):
        r = rows.get(sid)
        if r is None:
            n_missing += 1
            continue
        if _is_valid_classification(r):
            n_valid += 1
            if r["board_pred"] == manifest[sid]["class_index"]:
                n_correct += 1
        elif r["gated"] != 1 or r["capture_ok"] != 1 or r["no_sync"] == 1 or r["rx_clipped"] == 1:
            n_rejected += 1
        else:
            n_invalid += 1
    return {
        "expected": expected, "n_results": len(rows), "n_missing": n_missing,
        "n_valid": n_valid, "n_rejected": n_rejected, "n_invalid": n_invalid,
        "n_correct": n_correct,
        "coverage": (n_valid / expected) if expected else None,
        "correct_over_expected": (n_correct / expected) if expected else None,
        "end_to_end_accuracy": (n_correct / expected) if expected else None,
        "gated_accuracy": (n_correct / n_valid) if n_valid else None,
    }


def compute_prediction(rows, manifest, digital):
    """预测对照（缺口 1 + S1 修复）：board_pred vs 数字基线 recovered_pred，**只在有效行上**。

    - agreement_over_expected（主指标）= 有效一致预测数 / 24（分母恒为 expected）。
    - conditional_agreement（条件一致率，另列）= 有效一致预测数 / 有效行数 n_valid。
    - n_same_error：两者一致但都判错（同错，且错到同一个类）。
    - n_new_flip：数字基线正确但板端翻转（新增翻转）。
    - n_board_fix：数字基线错误但板端纠正（反向翻转，供参考）。
    未分类的 -1 / 门拒 / 非有限 / 未捕获行**不**被描述为「调制混淆」，只留在 expected=24。
    """
    expected = K_SOURCES
    n_valid = n_agree = n_same_error = n_new_flip = n_board_fix = 0
    for sid in sorted(manifest):
        r = rows.get(sid)
        if r is None or sid not in digital or not _is_valid_classification(r):
            continue
        n_valid += 1
        bp = r["board_pred"]
        rp = digital[sid]["recovered_pred"]
        ci = manifest[sid]["class_index"]
        if bp == rp:
            n_agree += 1
            if bp != ci:
                n_same_error += 1
        else:
            if rp == ci and bp != ci:
                n_new_flip += 1
            if rp != ci and bp == ci:
                n_board_fix += 1
    agreement_over_expected = (n_agree / expected) if expected else None
    conditional_agreement = (n_agree / n_valid) if n_valid else None
    return {"expected": expected, "n_valid": n_valid, "n_agree": n_agree,
            "n_same_error": n_same_error, "n_new_flip": n_new_flip,
            "n_board_fix": n_board_fix,
            "agreement_over_expected": agreement_over_expected,
            "conditional_agreement": conditional_agreement,
            "conditional_denominator": n_valid}


def judge(kind, manifest_path, results_path, summary_path, layers_dir, tensor_dir,
          digital_path, baseline_identity_path, out_json):
    analysis_errors = []
    measurement_errors = []

    def _abort_analysis(msg):
        verdict = {"token": TOKEN, "kind": kind, "analysis_ok": False,
                   "measurement_valid": False, "analysis_errors": [msg],
                   "measurement_errors": [],
                   "note": "analysis failed; no measurement verdict produced"}
        if out_json:
            out_json.write_text(json.dumps(verdict, indent=2, sort_keys=True),
                                encoding="utf-8")
        print("JUDGE_BOARD kind=%s analysis_ok=0 measurement_valid=0 "
              "analysis_errors=1 measurement_errors=0" % kind)
        print("  analysis_error: %s" % msg)
        print("JUDGE_BOARD_DONE")
        return 1

    try:
        manifest = load_manifest(Path(manifest_path))
        rows = load_results(Path(results_path))
        summary = load_summary(Path(summary_path))
        digital = load_digital_baseline(Path(digital_path)) if digital_path else None
        sidecar = None
        if digital is not None:
            if not baseline_identity_path:
                raise ValueError("--digital-baseline requires --baseline-identity "
                                 "(frozen baseline identity sidecar, S2)")
            sidecar = load_baseline_identity(Path(baseline_identity_path))
    except (ValueError, OSError) as e:
        return _abort_analysis(str(e))
    layers_dir_p = Path(layers_dir) if layers_dir else None
    tensor_dir_p = Path(tensor_dir) if tensor_dir else None

    # --- 身份一致性（分析级） ---
    identity_errors, missing = validate_identity(rows, manifest)
    analysis_errors.extend(identity_errors)
    if missing:
        measurement_errors.append("INCOMPLETE missing sources=%s (denominator stays %d)"
                                  % (missing, len(manifest)))
    if summary["capture_source"] != kind:
        analysis_errors.append("KIND_MISMATCH summary capture_source=%s != --kind=%s"
                               % (summary["capture_source"], kind))
    sid0 = min(manifest)
    if summary["source_id"] != manifest[sid0]["source_id"]:
        analysis_errors.append("SUMMARY_SOURCE_ID_MISMATCH %r != manifest %r"
                               % (summary["source_id"], manifest[sid0]["source_id"]))
    if summary["version"] != manifest[sid0]["conversion_version"]:
        analysis_errors.append("SUMMARY_VERSION_MISMATCH %r != manifest %r"
                               % (summary["version"], manifest[sid0]["conversion_version"]))
    if digital is not None:
        for sid in sorted(digital):
            m = manifest.get(sid)
            if m is None:
                analysis_errors.append("DIGITAL source_index=%d not in manifest" % sid)
            elif digital[sid]["class_index"] != m["class_index"] or \
                    digital[sid]["class_name"] != m["class_name"]:
                analysis_errors.append("DIGITAL_CLASS_MISMATCH source_index=%d" % sid)

    # --- 数字基线身份绑定（S2，分析级）：绑定 (source_id, version, manifest SHA, 模型身份) ---
    baseline_identity = None
    if digital is not None:
        entry, bind_errors = bind_baseline(manifest, manifest_path, digital_path, sidecar)
        analysis_errors.extend(bind_errors)
        baseline_identity = entry

    # --- 摘要漂移（测量级，fail-closed） ---
    st = recompute_stats(rows, manifest)
    for key, sfield in (("n_processed", "processed"), ("n_gated", "gated"),
                        ("n_no_sync", "no_sync"), ("n_rx_clipped", "rx_clipped"),
                        ("n_classified", "classified"), ("n_correct", "correct")):
        if st[key] != summary[sfield]:
            measurement_errors.append("SUMMARY_DRIFT %s recomputed=%d summary=%d"
                                      % (sfield, st[key], summary[sfield]))

    # --- 板端实际张量文件核验（缺口 2，测量级） ---
    tensor_ok, tensor_bad = verify_board_tensor_files(rows, tensor_dir_p)
    for b in tensor_bad:
        measurement_errors.append("TENSOR_FILE %s" % b)

    # --- 文件模式：逐字节一致 + 干净数字标志 + 数字基线 B 张量绑定 ---
    byte_identical = None
    digital_binding = None
    if kind == "file":
        ok, bad = verify_file_byte_identical(rows, layers_dir_p)
        byte_identical = {"ok": ok, "bad": bad, "total": ok + len(bad)}
        if ok != K_SOURCES:
            measurement_errors.append("FILE_BYTE_IDENTICAL %d/%d" % (ok, K_SOURCES))
        for sid in sorted(rows):
            r = rows[sid]
            if r["gated"] != 1 or r["finite"] != 1 or r["repeatable"] != 1:
                measurement_errors.append("FILE_CLEAN_DIGITAL_FLAG source_index=%d gated=%d "
                                          "finite=%d repeatable=%d (clean digital must be all-1)"
                                          % (sid, r["gated"], r["finite"], r["repeatable"]))
        if digital is not None:
            db_ok, db_bad = verify_digital_baseline_binding(manifest, digital, layers_dir_p)
            digital_binding = {"ok": db_ok, "bad": db_bad, "total": db_ok + len(db_bad)}
            if db_ok != K_SOURCES:
                measurement_errors.append("DIGITAL_BASELINE_BINDING %d/%d (digital B SHA "
                                          "!= --layers-dir bins)" % (db_ok, K_SOURCES))

    # --- 分类统计（S1，主指标分母恒 /24）+ 预测对照 vs 数字基线（缺口 1 + S1） ---
    classification = compute_classification(rows, manifest)
    prediction = None
    if digital is not None:
        prediction = compute_prediction(rows, manifest, digital)
        if kind == "file":
            if prediction["n_valid"] != K_SOURCES:
                measurement_errors.append("PREDICTION_COVERAGE n_valid=%d/%d (valid "
                                          "classifications should be 24/24 in clean digital)"
                                          % (prediction["n_valid"], K_SOURCES))
            if prediction["n_agree"] != K_SOURCES:
                measurement_errors.append("PREDICTION_DISAGREE board-vs-digital "
                                          "n_agree=%d new_flip=%d board_fix=%d "
                                          "agreement/24=%s"
                                          % (prediction["n_agree"],
                                             prediction["n_new_flip"],
                                             prediction["n_board_fix"],
                                             ("%.6f" % prediction["agreement_over_expected"])
                                             if prediction["agreement_over_expected"] is not None
                                             else "n/a"))

    # --- 本轮测量完整有效（缺口 3b） ---
    complete = (summary["completed"] == 1)
    functional = (summary["functional_pass"] == 1)
    n_results = len(rows)
    analysis_ok = not analysis_errors
    # 分析不一致时（身份/kind/source_id/version 不符），不担保本轮测量有效（fail-closed）。
    measurement_valid = analysis_ok and (not measurement_errors) and complete and \
        functional and (n_results == K_SOURCES) and (not missing)

    verdict = {
        "token": TOKEN,
        "kind": kind,
        "source_id": summary["source_id"],
        "version": summary["version"],
        "capture_source": summary["capture_source"],
        "n_sources": len(manifest),
        "n_results": n_results,
        "analysis_ok": analysis_ok,
        "measurement_valid": measurement_valid,
        "analysis_errors": analysis_errors,
        "measurement_errors": measurement_errors,
        "recomputed_stats": st,
        "summary": summary,
        "classification": classification,
        "byte_identical": byte_identical,
        "digital_binding": digital_binding,
        "baseline_identity": baseline_identity,
        "board_tensor_files": {"ok": tensor_ok, "bad": tensor_bad,
                               "total": tensor_ok + len(tensor_bad)},
        "prediction": prediction,
        "gate": {"training_residual_rel_limit": K_GATE,
                 "passed": sum(1 for r in rows.values()
                               if r["training_residual_rel"] <= K_GATE),
                 "total": len(rows)},
        "attribution": ("文件模式：板端 recovered tensor 与数字 B 层逐字节相同 + board_pred 与"
                        "数字基线 recovered_pred 24/24 一致为本次独立对照的可判据；设备模式："
                        "如实记录 board_pred vs class_index 与门/标签统计，不自动归因 RF"
                        "（RF 归因须板端训练块残差单独证据）。"),
    }
    if out_json:
        out_json.write_text(json.dumps(verdict, indent=2, sort_keys=True),
                            encoding="utf-8")

    print("JUDGE_BOARD kind=%s analysis_ok=%d measurement_valid=%d sources=%d results=%d "
          "analysis_errors=%d measurement_errors=%d" %
          (kind, 1 if analysis_ok else 0, 1 if measurement_valid else 0,
           len(manifest), len(rows), len(analysis_errors), len(measurement_errors)))
    print("JUDGE_BOARD stats processed=%d gated=%d gate_reject=%d hard_invalid=%d "
          "no_sync=%d rx_clipped=%d classified=%d correct=%d completed=%d "
          "functional_pass=%d" %
          (st["n_processed"], st["n_gated"], summary["gate_reject"],
           summary["hard_invalid"], st["n_no_sync"], st["n_rx_clipped"],
           st["n_classified"], st["n_correct"], summary["completed"],
           summary["functional_pass"]))
    print("JUDGE_BOARD classification expected=%d n_valid=%d n_missing=%d n_rejected=%d "
          "n_invalid=%d n_correct=%d coverage=%s correct/24=%s gated_acc=%s "
          "end_to_end=%s" %
          (classification["expected"], classification["n_valid"],
           classification["n_missing"], classification["n_rejected"],
           classification["n_invalid"], classification["n_correct"],
           _fmt(classification["coverage"]), _fmt(classification["correct_over_expected"]),
           _fmt(classification["gated_accuracy"]), _fmt(classification["end_to_end_accuracy"])))
    if byte_identical is not None:
        print("JUDGE_BOARD byte_identical=%d/%d" % (byte_identical["ok"],
                                                    byte_identical["total"]))
    if digital_binding is not None:
        print("JUDGE_BOARD digital_binding=%d/%d" % (digital_binding["ok"],
                                                     digital_binding["total"]))
    print("JUDGE_BOARD board_tensor_files=%d/%d" % (tensor_ok,
                                                    tensor_ok + len(tensor_bad)))
    if prediction is not None:
        print("JUDGE_BOARD prediction n_valid=%d n_agree=%d n_same_error=%d "
              "n_new_flip=%d n_board_fix=%d agreement/24=%s conditional=%s" %
              (prediction["n_valid"], prediction["n_agree"],
               prediction["n_same_error"], prediction["n_new_flip"],
               prediction["n_board_fix"], _fmt(prediction["agreement_over_expected"]),
               _fmt(prediction["conditional_agreement"])))
    for e in analysis_errors:
        print("  analysis_error: %s" % e)
    for e in measurement_errors:
        print("  measurement_error: %s" % e)
    print("JUDGE_BOARD_DONE")
    if not analysis_ok:
        return 1
    if not measurement_valid:
        return 2
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", default="file", choices=["file", "device"])
    ap.add_argument("--manifest", default="")
    ap.add_argument("--results", default="")
    ap.add_argument("--summary", default="")
    ap.add_argument("--layers-dir", default=None)
    ap.add_argument("--tensor-dir", default=None)
    ap.add_argument("--digital-baseline", default=None)
    ap.add_argument("--baseline-identity", default=None,
                    help="frozen digital baseline identity sidecar JSON (S2; required "
                         "whenever --digital-baseline is used)")
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.manifest or not args.results or not args.summary:
        ap.error("--manifest, --results and --summary are required (or --self-test)")
    if not args.tensor_dir:
        ap.error("--tensor-dir is required (board $OUT directory with "
                 "<sid>.recovered.tensor.bin files)")
    if args.kind == "file":
        if not args.layers_dir:
            ap.error("--kind file requires --layers-dir (digital B-layer reference bins)")
        if not args.digital_baseline:
            ap.error("--kind file requires --digital-baseline (host digital replay tsv, "
                     "19 cols with recovered_pred)")
        if not args.baseline_identity:
            ap.error("--kind file requires --baseline-identity (frozen baseline identity "
                     "sidecar, S2)")
    elif args.digital_baseline and not args.baseline_identity:
        ap.error("--digital-baseline requires --baseline-identity (frozen baseline identity "
                 "sidecar, S2)")
    return judge(args.kind, Path(args.manifest), Path(args.results),
                 Path(args.summary),
                 Path(args.layers_dir) if args.layers_dir else None,
                 Path(args.tensor_dir),
                 Path(args.digital_baseline) if args.digital_baseline else None,
                 Path(args.baseline_identity) if args.baseline_identity else None,
                 Path(args.out_json) if args.out_json else None)


def _write_tmp_tsv(d, name, header, rows):
    p = d / name
    p.write_text(header + "\n" + "".join(rows), encoding="utf-8")
    return p


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-56s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        recovered_bytes = b"r" * 64
        RECOVERED_SHA = sha256_bytes(recovered_bytes)

        # manifest: 24 rows, source_index == class_index+1
        mh = MANIFEST_HEADER + "\n"
        ml = []
        for i in range(1, 25):
            ml.append("fix1-public-protocol-24waveforms\tv1\t%d\t%d\tC%02d\t%d\t"
                      "%d.burst.i16\t%s\t%s\t%s\n" %
                      (i, i - 1, i - 1, 1000 + i - 1, i,
                       "b" * 64, "p" * 64, "a" * 64))
        manifest = _write_tmp_tsv(d, "manifest.tsv", mh.rstrip("\n"), ml)

        # results: 24 rows, all clean, board_pred == class_index
        rh = RESULT_HEADER + "\n"
        def _mk_result(i, sha, pred=None):
            p = (i - 1) if pred is None else pred
            return "%d\t%d\tC%02d\t0\t0.0\t0.0\t0.0\t1.0\t0.0\t0.0\t0.0\t0.0\t0.001\t" \
                   "1\t1\t1\t%d\t1\t0\t0\t%s\t%s\t%s\n" % \
                   (i, i - 1, i - 1, p, "x" * 64, "y" * 64, sha)
        def _mk_result_flags(i, sha, pred=None, gated=1, finite=1, capture_ok=1,
                             no_sync=0, rx_clipped=0):
            p = (i - 1) if pred is None else pred
            return "%d\t%d\tC%02d\t0\t0.0\t0.0\t0.0\t1.0\t0.0\t0.0\t0.0\t0.0\t0.001\t" \
                   "%d\t%d\t1\t%d\t%d\t%d\t%d\t%s\t%s\t%s\n" % \
                   (i, i - 1, i - 1, gated, finite, p, capture_ok, no_sync, rx_clipped,
                    "x" * 64, "y" * 64, sha)
        rl = [_mk_result(i, RECOVERED_SHA) for i in range(1, 25)]
        results = _write_tmp_tsv(d, "results.tsv", rh.rstrip("\n"), rl)

        # summary: 22 cols, matches recompute
        sh = SUMMARY_HEADER + "\n"
        sl = ["24\t24\t24\t0\t0\t0\t0\t24\t24\t1\t0\t\t1\t1\t1\t1\t0.001\t0.01\t"
              "1\tfix1-public-protocol-24waveforms\tv1\tfile\n"]
        summary = _write_tmp_tsv(d, "summary.tsv", sh.rstrip("\n"), sl)

        # layers-dir (digital B-layer reference) + tensor-dir (board $OUT)
        layers = d / "layers"
        layers.mkdir()
        tensors = d / "tensors"
        tensors.mkdir()
        for i in range(1, 25):
            (layers / ("%d%s" % (i, TENSOR_SUFFIX))).write_bytes(recovered_bytes)
            (tensors / ("%d%s" % (i, TENSOR_SUFFIX))).write_bytes(recovered_bytes)

        # digital baseline: 24 rows, recovered_pred == class_index, sha == RECOVERED_SHA
        dh = DIGITAL_HEADER + "\n"
        def _mk_digital(i, sha, pred=None):
            p = (i - 1) if pred is None else pred
            return "%d\t%d\tC%02d\t%d\t1\t%d\t1\t%d\t1\t1\t1.0\t0.0\t0.0\t1.0\t0.0\t" \
                   "0.0\t0.999\t0.001\t%s\n" % (i, i - 1, i - 1, i - 1, p, i - 1, sha)
        dl = [_mk_digital(i, RECOVERED_SHA) for i in range(1, 25)]
        digital = _write_tmp_tsv(d, "digital.tsv", dh.rstrip("\n"), dl)

        def _mk_sidecar(name, baselines, model=None):
            data = {
                "model": model if model is not None else
                    {"json_sha256": FROZEN_MODEL_JSON_SHA, "raw_sha256": FROZEN_MODEL_RAW_SHA},
                "baselines": baselines,
            }
            p = d / name
            p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
            return p

        # --- S2 fixtures: v2 manifest/digital/results/summary (one known baseline error) ---
        ml_v2 = []
        for i in range(1, 25):
            ml_v2.append("fix1v2-waveform-corrected-24waveforms\tv2\t%d\t%d\tC%02d\t%d\t"
                         "%d.burst.i16\t%s\t%s\t%s\n" %
                         (i, i - 1, i - 1, 1000 + i - 1, i, "b" * 64, "p" * 64, "a" * 64))
        manifest_v2 = _write_tmp_tsv(d, "manifest_v2.tsv", mh.rstrip("\n"), ml_v2)

        # digital_v2: source 20 has one known error (recovered_pred=16 != class 19)
        dl_v2 = [_mk_digital(i, RECOVERED_SHA, pred=16) if i == 20
                 else _mk_digital(i, RECOVERED_SHA) for i in range(1, 25)]
        digital_v2 = _write_tmp_tsv(d, "digital_v2.tsv", dh.rstrip("\n"), dl_v2)

        # results_v2: source 20 board_pred=16 (reproduces the same baseline error)
        rl_v2 = [_mk_result(i, RECOVERED_SHA, pred=16) if i == 20
                 else _mk_result(i, RECOVERED_SHA) for i in range(1, 25)]
        results_v2 = _write_tmp_tsv(d, "results_v2.tsv", rh.rstrip("\n"), rl_v2)

        # summary_v2: correct=23 (source 20 wrong)
        sl_v2 = ["24\t24\t24\t0\t0\t0\t0\t24\t23\t1\t0\t\t1\t1\t1\t1\t0.001\t0.01\t"
                 "1\tfix1v2-waveform-corrected-24waveforms\tv2\tfile\n"]
        summary_v2 = _write_tmp_tsv(d, "summary_v2.tsv", sh.rstrip("\n"), sl_v2)

        # sidecar: v1 + v2 identity records (model = frozen BF16)
        sidecar = _mk_sidecar("baseline_identity.json", {
            "fix1-public-protocol-24waveforms/v1": {
                "source_id": "fix1-public-protocol-24waveforms",
                "conversion_version": "v1",
                "manifest_sha256": sha256_bytes(manifest.read_bytes()),
                "baseline_tsv_sha256": sha256_bytes(digital.read_bytes()),
            },
            "fix1v2-waveform-corrected-24waveforms/v2": {
                "source_id": "fix1v2-waveform-corrected-24waveforms",
                "conversion_version": "v2",
                "manifest_sha256": sha256_bytes(manifest_v2.read_bytes()),
                "baseline_tsv_sha256": sha256_bytes(digital_v2.read_bytes()),
            },
        })

        # (1) file mode all clean -> rc=0
        rc = judge("file", manifest, results, summary, layers, tensors, digital,
                   sidecar, d / "out1.json")
        check("file all-clean -> rc=0", rc == 0, "rc=%d" % rc)

        # (2) one TSV SHA drift -> byte_identical + tensor mismatch -> rc=2
        results_bad = _write_tmp_tsv(d, "results_bad.tsv", rh.rstrip("\n"),
                                     [l.replace(RECOVERED_SHA, "z" * 64, 1) for l in rl])
        rc2 = judge("file", manifest, results_bad, summary, layers, tensors, digital,
                    sidecar, d / "out2.json")
        check("one SHA drift -> rc=2", rc2 == 2, "rc=%d" % rc2)

        # (3) summary drift (correct 24->23) -> rc=2
        sl2 = ["24\t24\t24\t0\t0\t0\t0\t24\t23\t1\t0\t\t1\t1\t1\t1\t0.001\t0.01\t"
               "1\tfix1-public-protocol-24waveforms\tv1\tfile\n"]
        summary2 = _write_tmp_tsv(d, "summary2.tsv", sh.rstrip("\n"), sl2)
        rc3 = judge("file", manifest, results, summary2, layers, tensors, digital,
                    sidecar, d / "out3.json")
        check("summary drift (correct 24->23) -> rc=2", rc3 == 2, "rc=%d" % rc3)

        # (4) device mode: no layers/digital, tensor files match -> rc=0
        sd = ["24\t24\t24\t0\t0\t0\t0\t24\t24\t1\t0\t\t1\t1\t1\t1\t0.001\t0.01\t"
              "1\tfix1-public-protocol-24waveforms\tv1\tdevice\n"]
        summary_d = _write_tmp_tsv(d, "summary_d.tsv", sh.rstrip("\n"), sd)
        rc4 = judge("device", manifest, results, summary_d, None, tensors, None, None,
                    d / "out4.json")
        check("device mode stats rc=0", rc4 == 0, "rc=%d" % rc4)

        # (5) duplicate source_index in results -> loader raises (缺口 3a)
        dup_lines = rl + [rl[0]]
        results_dup = _write_tmp_tsv(d, "results_dup.tsv", rh.rstrip("\n"), dup_lines)
        try:
            load_results(results_dup)
            check("duplicate source_index -> raises", False, "did not raise")
        except ValueError as e:
            check("duplicate source_index -> raises", "duplicate" in str(e), str(e))

        # (6) missing board tensor file -> rc=2 (缺口 2)
        tensors_missing = d / "tensors_missing"
        tensors_missing.mkdir()
        for i in range(1, 25):
            if i == 7:
                continue
            (tensors_missing / ("%d%s" % (i, TENSOR_SUFFIX))).write_bytes(recovered_bytes)
        rc6 = judge("file", manifest, results, summary, layers, tensors_missing, digital,
                    sidecar, d / "out6.json")
        check("missing board tensor file -> rc=2", rc6 == 2, "rc=%d" % rc6)

        # (7) prediction new flip (board flips a host-correct frame) -> rc=2 + n_new_flip=1
        rl_flip = [_mk_result(i, RECOVERED_SHA) for i in range(1, 25)]
        rl_flip[6] = _mk_result(7, RECOVERED_SHA, pred=23)  # src=7 board_pred=23 != class 6
        results_flip = _write_tmp_tsv(d, "results_flip.tsv", rh.rstrip("\n"), rl_flip)
        out7 = d / "out7.json"
        rc7 = judge("file", manifest, results_flip, summary, layers, tensors, digital,
                    sidecar, out7)
        v7 = json.loads(out7.read_text(encoding="utf-8"))
        check("prediction new flip -> rc=2 and n_new_flip=1",
              rc7 == 2 and v7["prediction"]["n_new_flip"] == 1 and
              v7["prediction"]["n_agree"] == 23 and not v7["measurement_valid"],
              "rc=%d new_flip=%d agree=%d" % (rc7, v7["prediction"]["n_new_flip"],
                                              v7["prediction"]["n_agree"]))

        # (8) KIND_MISMATCH (summary device vs --kind file) -> analysis fail -> rc=1
        rc8 = judge("file", manifest, results, summary_d, layers, tensors, digital,
                    sidecar, d / "out8.json")
        check("kind mismatch -> analysis fail -> rc=1", rc8 == 1, "rc=%d" % rc8)

        # --- S1 regression: 主指标分母 /24，缺行/非有限行不计入一致 ---
        man_m = load_manifest(manifest)
        dig_m = load_digital_baseline(digital)

        # (9) one missing row -> agreement_over_expected = 23/24 (not 1.0)
        rl_missing = [_mk_result(i, RECOVERED_SHA) for i in range(1, 25) if i != 7]
        results_missing = _write_tmp_tsv(d, "results_missing.tsv", rh.rstrip("\n"), rl_missing)
        rows_m = load_results(results_missing)
        cls_m = compute_classification(rows_m, man_m)
        pr_m = compute_prediction(rows_m, man_m, dig_m)
        check("S1 missing row -> agreement/24=23/24 (n_missing=1)",
              pr_m["agreement_over_expected"] is not None and
              abs(pr_m["agreement_over_expected"] - 23.0 / 24.0) < 1e-9 and
              cls_m["n_missing"] == 1 and pr_m["n_agree"] == 23 and
              pr_m["conditional_agreement"] == 1.0,
              "agreement/24=%s n_missing=%d" %
              (pr_m["agreement_over_expected"], cls_m["n_missing"]))

        # (10) one finite=0 + capture_ok=0 row (retaining matching board_pred) -> 23/24
        rl_nonfin = [_mk_result_flags(i, RECOVERED_SHA, finite=0, capture_ok=0) if i == 7
                     else _mk_result(i, RECOVERED_SHA) for i in range(1, 25)]
        results_nonfin = _write_tmp_tsv(d, "results_nonfin.tsv", rh.rstrip("\n"), rl_nonfin)
        rows_nf = load_results(results_nonfin)
        cls_nf = compute_classification(rows_nf, man_m)
        pr_nf = compute_prediction(rows_nf, man_m, dig_m)
        check("S1 nonfinite+capture_ok=0 row -> agreement/24=23/24",
              pr_nf["agreement_over_expected"] is not None and
              abs(pr_nf["agreement_over_expected"] - 23.0 / 24.0) < 1e-9 and
              pr_nf["n_agree"] == 23 and pr_nf["n_valid"] == 23 and
              cls_nf["n_rejected"] == 1 and cls_nf["n_invalid"] == 0,
              "agreement/24=%s n_valid=%d n_rejected=%d n_invalid=%d" %
              (pr_nf["agreement_over_expected"], pr_nf["n_valid"],
               cls_nf["n_rejected"], cls_nf["n_invalid"]))

        # --- S2 baseline identity binding ---
        # (11) correct v2 combo accepted even with one known baseline classification error
        rc11 = judge("file", manifest_v2, results_v2, summary_v2, layers, tensors,
                     digital_v2, sidecar, d / "out11.json")
        v11 = json.loads((d / "out11.json").read_text(encoding="utf-8"))
        check("S2 correct v2 combo accepted (one known error -> n_same_error=1)",
              rc11 == 0 and v11["measurement_valid"] and
              v11["prediction"]["n_agree"] == 24 and
              v11["prediction"]["n_same_error"] == 1 and
              v11["classification"]["n_correct"] == 23,
              "rc=%d n_agree=%d n_same_error=%d n_correct=%d" %
              (rc11, v11["prediction"]["n_agree"], v11["prediction"]["n_same_error"],
               v11["classification"]["n_correct"]))

        # (12) v1 digital baseline + v2 manifest/summary -> reject (BASELINE_TSV_SHA_MISMATCH)
        rc12 = judge("file", manifest_v2, results_v2, summary_v2, layers, tensors,
                     digital, sidecar, d / "out12.json")
        v12 = json.loads((d / "out12.json").read_text(encoding="utf-8"))
        check("S2 v1 baseline + v2 manifest -> reject (BASELINE_TSV_SHA_MISMATCH)",
              rc12 == 1 and not v12["analysis_ok"] and not v12["measurement_valid"] and
              any("BASELINE_TSV_SHA_MISMATCH" in e for e in v12["analysis_errors"]),
              "rc=%d errors=%s" % (rc12, v12["analysis_errors"]))

        # (13) wrong declared model identity -> reject (BASELINE_MODEL_IDENTITY_MISMATCH)
        sidecar_bad = _mk_sidecar("sidecar_bad.json", {
            "fix1-public-protocol-24waveforms/v1": {
                "source_id": "fix1-public-protocol-24waveforms",
                "conversion_version": "v1",
                "manifest_sha256": sha256_bytes(manifest.read_bytes()),
                "baseline_tsv_sha256": sha256_bytes(digital.read_bytes()),
            },
        }, model={"json_sha256": "0" * 64, "raw_sha256": "0" * 64})
        rc13 = judge("file", manifest, results, summary, layers, tensors, digital,
                     sidecar_bad, d / "out13.json")
        v13 = json.loads((d / "out13.json").read_text(encoding="utf-8"))
        check("S2 model identity mismatch -> reject",
              rc13 == 1 and
              any("BASELINE_MODEL_IDENTITY_MISMATCH" in e for e in v13["analysis_errors"]),
              "rc=%d errors=%s" % (rc13, v13["analysis_errors"]))

    all_ok = all(checks)
    print("RADIOML_INDEPENDENT_RX_BOARD_JUDGER_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
