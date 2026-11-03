#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_radioml_singlesdr_ab1.py -- 主机测试 (fix10class24-original-radioml-singlesdr-ab1)。

g++ 在本 Windows 主机不可用, 板端 C++ 在 aarch64 编译; 故本测试为 Python-only, 覆盖
任务书要求的最小主机不变量 (纯离线只读, 不碰板/不发射/不训练):

  1. 480 帧主键唯一 + 身份 (与 npu-ab1 逐字节一致)。
  2. short24 固定选取 (每类 1 帧 @30 dB, 最小 selection_id)。
  3. 适配确定性 + 类无关 + 循环铺排近似保 RMS。
  4. TX payload 与 dualsdr 分支 results/tx_payload 逐字节一致 (证明契约 VENDOR 无漂移)。
  5. loader 契约常量与导出逐字一致 (adaptation tag / 18 列表头 / 480 / 53760 / clip==0)。
  6. runner 红线源码审计 (单 SDR 本地 TX 非 PC-TX / 生产恢复 / RX 35 dB 默认 /
     TX -40 上限 / 采样 2.56M 守卫 / rf-path=direct-cable 守卫 / out-dir 反覆盖 /
     末次重捕 / 板端绝不强制 / 窗口=恢复 payload[:1024]*unscale)。
  7. 冻结模型 SHA。
  8. run 脚本源码审计 (显式 --rx-gain=35 覆盖 / --rf-path / phase 名 / 24 类模型覆盖)。
  9. 四臂判定器自测 (gate-reject 分母不剔除 / hard_invalid 绝不强制 / C 臂缺席=PENDING)。
  10. 门拒+hard-invalid 样本同样落盘原始捕获+恢复诊断 (源码审计, 落盘在过门分支之前)。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import radioml_dualsdr_common as C  # noqa: E402
import radioml_dualsdr_burst as B  # noqa: E402
from export_radioml_dualsdr_tx_payload import (  # noqa: E402
    parse_npu_ab_manifest, build_tx_payload, TX_MANIFEST_HEADER)

NPU_AB = Path(r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work"
              r"\sdr_rml24_fix10class24_original_radioml_npu_ab1\input_package")
DUALSDR_TX = Path(r"F:\嵌赛\fix10class24_original_radioml_dualsdr_ab1_work"
                  r"\results\tx_payload")

RUNNER = ROOT / "board_package" / "radioml_singlesdr_ab_runner.hpp"
LOADER = ROOT / "board_package" / "radioml_singlesdr_ab_loader.hpp"
RUN_SH = SCRIPTS / "run_radioml_singlesdr_ab.sh"

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


def run_py(args):
    return subprocess.run([sys.executable, "-I", str(SCRIPTS / args[0])] + args[1:],
                          capture_output=True, text=True)


@test
def t01_real480_identity_unique():
    frames = parse_npu_ab_manifest(NPU_AB / "manifest.tsv")
    assert len(frames) == 480
    assert len({f["hdf5_row_index"] for f in frames}) == 480
    assert len({f["input_file"] for f in frames}) == 480
    assert len({f["model_input_sha256"] for f in frames}) == 480
    assert all(0 <= f["raw24_class"] < 24 for f in frames)
    assert all(f["dataset_snr_db"] in (0, 10, 20, 30) for f in frames)
    from collections import Counter
    c = Counter((f["raw24_class"], f["dataset_snr_db"]) for f in frames)
    assert all(v == 5 for v in c.values()), "expected 5 frames per (class,snr)"


@test
def t02_short24_selection():
    frames = parse_npu_ab_manifest(NPU_AB / "manifest.tsv")
    sel = C.short24_selection(frames)
    assert len(sel) == 24
    assert len({f["raw24_class"] for f in sel}) == 24
    assert all(f["dataset_snr_db"] == 30 for f in sel)


@test
def t03_adaptation_class_agnostic_deterministic():
    rng = np.random.default_rng(7)
    iq = rng.standard_normal(1024) + 1j * rng.standard_normal(1024)
    assert np.array_equal(C.cyclic_tile_1024_to_payload(iq),
                          C.cyclic_tile_1024_to_payload(iq))
    assert np.array_equal(build_tx_payload(iq)["payload_i16"],
                          build_tx_payload(iq)["payload_i16"])
    tiled = C.cyclic_tile_1024_to_payload(iq)
    assert tiled.size == C.RF_PAYLOAD_COMPLEX
    assert np.allclose(tiled[:1024], iq)
    assert abs(C.native_rms(tiled) - C.native_rms(iq)) < 0.02 * C.native_rms(iq)


@test
def t04_tx_payload_vendored_byte_identical():
    """本任务 VENDOR 的契约必须逐字节复现 dualsdr 分支已导出的 payload。"""
    assert DUALSDR_TX.exists(), "dualsdr results/tx_payload missing"
    frames = parse_npu_ab_manifest(NPU_AB / "manifest.tsv")
    # 抽验全 480 帧 + 首尾各 1: 每一帧 .i16 字节必须与 dualsdr 分支一致。
    for fr in frames:
        iq = C.load_tensor_2x1024(NPU_AB / fr["input_file"])
        ev = build_tx_payload(iq)
        mine = ev["payload_i16"].tobytes()
        theirs = (DUALSDR_TX / ("%d.i16" % fr["selection_id"])).read_bytes()
        assert mine == theirs, "vendored contract drift at selection_id=%d" % fr["selection_id"]


@test
def t05_loader_contract_constants():
    """loader 的冻结契约常量必须与导出脚本逐字一致。"""
    src = LOADER.read_text(encoding="utf-8")
    assert "kFrameCount = 480" in src
    assert "kPayloadComplex = 53760" in src
    assert "cyclic_tile_1024_to_53760_rms2048_ci16" in src
    assert "fr.clip_pre != 0 || fr.clip_post != 0" in src
    assert "tx_manifest.tsv" in src
    # loader 18 列表头字面量必须包含全部 18 个列名 (源码用 \t 转义, 编译后等于
    # "\t".join(TX_MANIFEST_HEADER)); 逐列核验列名在位。
    for col in TX_MANIFEST_HEADER:
        assert col in src, "loader header literal missing column %s" % col
    # 实际生成的 tx_manifest.tsv 首行必须逐字等于 TX_MANIFEST_HEADER (导出==契约)。
    header_line = (DUALSDR_TX / "tx_manifest.tsv").read_text(encoding="utf-8") \
        .split("\n", 1)[0].rstrip("\r")
    assert header_line == "\t".join(TX_MANIFEST_HEADER)


@test
def t06_runner_red_line_source_audit():
    src = RUNNER.read_text(encoding="utf-8")
    # 单 SDR 本地 TX (非 PC-TX 控制通道)
    assert "transfer_one_attempt_rf_24class_bf16_fix10" in src
    # 生产恢复
    assert "recover_payload_with_coarse_cfo" in src
    # RX 手动增益默认 35 dB
    assert 'board::opt_d(argc, argv, "--rx-gain", 35.0)' in src
    # TX 衰减 -40 硬上限
    assert "tx_atten_db > pluto::kSafeTxCeilingDb" in src
    # 采样率 2.56 Msps 守卫
    assert "sample_rate != 2560000LL" in src
    # rf-path 必须 direct-cable
    assert 'rf_path != "direct-cable"' in src
    # out-dir 反覆盖
    assert "--out-dir already exists" in src
    # 末次重捕策略
    assert "should_retry_payload_training_capture" in src
    # 板端绝不强制分类
    assert "board_pred = finite ? raw_top : -1;" in src
    # 模型窗口 = 恢复 payload[:1024] * unscale (非 D2-restore)
    assert "payload[k].real() * fr.unscale" in src


@test
def t07_frozen_model_identity():
    assert C.FROZEN_MODEL_JSON_SHA == \
        "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
    assert C.FROZEN_MODEL_RAW_SHA == \
        "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
    assert C.FROZEN_CKPT_SHA == \
        "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"


@test
def t08_run_script_source_audit():
    src = RUN_SH.read_text(encoding="utf-8")
    assert "radioml-original-singlesdr-ab-24class-bf16-fix10" in src
    # 显式 --rx-gain=35 (覆盖 run_gate9_rml23.sh 默认 --rx-gain=10)
    assert "--rx-gain=\"$RX_GAIN_DB\"" in src
    assert 'RX_GAIN_DB=35.0' in src
    assert "--rf-path=\"$RF_PATH\"" in src
    assert 'RF_PATH="direct-cable"' in src
    assert 'TX_ATTEN_DB=-40.0' in src
    assert "--model-json=\"$MODEL_JSON\"" in src and "--model-raw=\"$MODEL_RAW\"" in src
    assert 'MODEL_JSON_SHA="28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"' in src


@test
def t09_four_arm_judger_denominator():
    frames = parse_npu_ab_manifest(NPU_AB / "manifest.tsv")
    by_id = {f["selection_id"]: f for f in frames}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)

        # 合成 digital.tsv (digital_pred = label, 全 480 -> D 臂 100%)
        dig = td / "digital.tsv"
        with open(dig, "w", encoding="utf-8") as f:
            f.write("selection_id\tdigital_pred\n")
            for sid in sorted(by_id):
                f.write("%d\t%d\n" % (sid, by_id[sid]["raw24_class"]))

        # 合成单 SDR board.tsv (19 列契约): 帧1 门拒可强制 / 帧2 门拒 hard_invalid /
        # 帧3 门内错误 / 其余门内正确
        board = td / "board_singlesdr.tsv"
        with open(board, "w", encoding="utf-8") as f:
            f.write("selection_id\thdf5_row_index\traw24_class\tdataset_snr_db\tgated\t"
                    "board_pred\tfinite\tresidual\tcorr\tcoarse_cfo_hz\tfine_cfo_hz\t"
                    "total_cfo_hz\tfractional_timing_samples\tclip\tcapture_attempts\t"
                    "gate_reject\thard_invalid\ttx_stop_ok\trx_restore_ok\n")
            for sid in sorted(by_id):
                fr = by_id[sid]
                if sid == 1:
                    row = [sid, fr["hdf5_row_index"], fr["raw24_class"], fr["dataset_snr_db"],
                           0, -1, 0, 0.15, 0.990, 0, 0, 0, 0, 0, 3, 1, 0, 1, 1]
                elif sid == 2:
                    row = [sid, fr["hdf5_row_index"], fr["raw24_class"], fr["dataset_snr_db"],
                           0, -1, 0, 0.30, 0.500, 0, 0, 0, 0, 3, 1, 1, 1, 1, 1]
                elif sid == 3:
                    row = [sid, fr["hdf5_row_index"], fr["raw24_class"], fr["dataset_snr_db"],
                           1, (fr["raw24_class"] + 1) % 24, 1, 0.06, 0.998, 0, 0, 0, 0, 0, 1, 0, 0, 1, 1]
                else:
                    row = [sid, fr["hdf5_row_index"], fr["raw24_class"], fr["dataset_snr_db"],
                           1, fr["raw24_class"], 1, 0.05, 0.999, 0, 0, 0, 0, 0, 1, 0, 0, 1, 1]
                f.write("\t".join(str(v) for v in row) + "\n")

        jd = td / "judge"
        r = run_py(["judge_radioml_singlesdr.py", "--input-package", str(NPU_AB),
                    "--digital", str(dig), "--board-singlesdr", str(board),
                    "--out-dir", str(jd)])
        assert r.returncode == 0, r.stderr
        s = json.loads((jd / "judge_summary.json").read_text())
        # S 臂覆盖全 480 (gate-reject 不从分母剔除)
        assert s["coverage"]["S"] == 480
        # 门内 478 (除帧1,2), 门内正确 477 (帧3 错) -> e2e = 477/480
        assert abs(s["accuracy"]["S"]["end_to_end_gate_reject_is_fail"] - 477/480) < 1e-9
        assert abs(s["accuracy"]["S"]["gated_accuracy"] - 477/478) < 1e-9
        # 可强制 = 门拒且非 hard_invalid = 仅帧1
        assert s["accuracy"]["S"]["gate_reject_forceable_count"] == 1
        assert s["accuracy"]["S"]["hard_invalid_count"] == 1
        # C 臂缺席 = PENDING, 不虚构数字
        assert s["arm_c_board_pending"] is True
        assert s["coverage"]["C"] == 0
        # arm A 参考 = Host BF16 419/480
        assert abs(s["accuracy"]["A_host_bf16_reference"] - 419/480) < 1e-9
        # D 臂 = 数字回环 480/480
        assert abs(s["accuracy"]["D_digital_e2e"] - 1.0) < 1e-9
        # 混淆 S 存在且 24x24
        conf = (jd / "confusion_s.tsv").read_text().strip().split("\n")
        assert len(conf) == 25, "24 classes + header"


@test
def t10_gate_reject_raw_capture_and_diag_saved():
    """门拒 + hard-invalid 样本同样落盘原始捕获 + 恢复诊断 (不只在过门分支)。

    任务书要求「保存所有样本的原始捕获+恢复诊断+模型输入+24 logits」。本测试为源码审计:
    runner 必须在过门分支之前无条件写 <sid>.raw.i16 (原始捕获) 与 <sid>.diag.json
    (恢复诊断), 使 gate-reject/hard-invalid 帧也落盘, 离线可复查而非重新采集。
    gate-reject/hard-invalid 仍计入分母, 绝不剔除 (t09 已证)。
    """
    src = RUNNER.read_text(encoding="utf-8")
    lines = src.splitlines()

    def first_idx(sub):
        for i, l in enumerate(lines):
            if sub in l:
                return i
        return -1

    raw_i = first_idx(".raw.i16")
    diag_i = first_idx(".diag.json")
    gated_i = first_idx("if (gated) {")
    assert raw_i >= 0, "runner must write a per-sample raw capture (.raw.i16)"
    assert diag_i >= 0, "runner must write a per-sample recovery diagnostic (.diag.json)"
    assert gated_i >= 0
    # 两处落盘都在过门分支之前 => 无条件执行, 覆盖 gate-reject / hard-invalid。
    assert raw_i < gated_i, "raw capture save must be OUTSIDE the gated branch"
    assert diag_i < gated_i, "diagnostic save must be OUTSIDE the gated branch"
    # 诊断记录携带恢复字段 (而非仅 19 列行); recovery_valid 仅出现在 diag 块。
    assert "payload_training_residual" in src
    assert "recovery_valid" in src
    assert "failure_token" in src


@test
def t11_result_rows_survive_capture_try_scope():
    """Source regression guard; board C++ compilation is still required."""
    src = RUNNER.read_text(encoding="utf-8")
    declaration = "std::vector<std::string> row_lines;"
    assert src.count(declaration) == 1
    capture_try = src.index("try {", src.index("bool all_capture_ok = true;"))
    assert src.index(declaration) < capture_try
    assert src.index("row_lines.push_back") > capture_try
    assert src.index("for (const auto& line : row_lines)") > src.index(
        "rep.last_res = m22::read_resources();")


def main():
    passed = 0
    for t in TESTS:
        try:
            t()
            print("PASS %s" % t.__name__)
            passed += 1
        except Exception as e:  # noqa: BLE001
            import traceback
            print("FAIL %s: %s" % (t.__name__, e))
            traceback.print_exc()
    print("RADIOML_SINGLESDR_AB1_SELFTEST %d/%d passed" % (passed, len(TESTS)))
    sys.exit(0 if passed == len(TESTS) else 1)


if __name__ == "__main__":
    main()
