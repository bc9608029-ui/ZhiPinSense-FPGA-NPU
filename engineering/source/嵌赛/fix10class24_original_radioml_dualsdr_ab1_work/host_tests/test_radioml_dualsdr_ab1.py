#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_radioml_dualsdr_ab1.py -- 主机测试 (fix10class24-original-radioml-dualsdr-ab1)。

覆盖任务书要求的最小主机不变量 (均对真实 480 帧包, 纯离线):
  1. 480 帧主键唯一 + 身份。
  2. short24 固定选取 / full480 无过滤。
  3. 类别/SNR 绝不用于恢复或预测 (适配函数只收 IQ, 确定性, 无标签分支)。
  4. RMS 上限 2048 / TX 衰减 -40 硬上限 + 裁剪记录。
  5. out-dir 反覆盖。
  6. gate-reject / hard-invalid 不从 e2e 分母剔除; hard_invalid 绝不强制。
  7. 所有捕获可追溯 (每帧 TX payload / recovered 输入有 SHA)。
  8. 数字回环非 byte-identical -> 报告不把量化差误归因于 RF。
  9. loader 契约常量 (18 列表头 / 480 / 53760 / clip==0 / 适配 tag)。
  10. arm C runner 红线源码审计 (RX-only 无 TX / 生产恢复 / RX 35 dB /
      RX BW 18M / 采样 2.56M 守卫 / rf-path direct-cable 守卫 /
      out-dir 反覆盖 / 末次重捕 / 板端绝不强制 / 窗口=恢复 payload[:1024]*unscale)。
  11. 板端 producer 接线 (gate9_phase.hpp phase + board_gate9 include/wrapper/dispatch)。
  12. run 脚本源码审计 (--tx-control / --rx-uri / --rx-gain=35 / --rx-bw=18M)。
  13. 门拒 + hard-invalid 样本同样落盘原始捕获 + 恢复诊断 (落盘在过门分支之前)。
  14. board_results 行生存于 capture try 作用域之外 (源码回归守卫)。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import radioml_dualsdr_common as C  # noqa: E402
import radioml_dualsdr_burst as B  # noqa: E402
from export_radioml_dualsdr_tx_payload import (  # noqa: E402
    parse_npu_ab_manifest, build_tx_payload, TX_MANIFEST_HEADER)

NPU_AB = Path(r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work"
              r"\sdr_rml24_fix10class24_original_radioml_npu_ab1\input_package")
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "board_package" / "radioml_dualsdr_ab_runner.hpp"
LOADER = ROOT / "board_package" / "radioml_dualsdr_ab_loader.hpp"
GATE9_PHASE = ROOT / "board_package" / "gate9_phase.hpp"
BOARD_GATE9 = ROOT / "board_package" / "board_gate9_full_chain_rml23.cpp"
RUN_SH_FULL = SCRIPTS / "run_radioml_dualsdr_full480.sh"
RUN_SH_SHORT = SCRIPTS / "run_radioml_dualsdr_short24.sh"
DUALSDR_TX = Path(r"F:\嵌赛\fix10class24_original_radioml_dualsdr_ab1_work"
                  r"\results\tx_payload")

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
    assert np.allclose(tiled[1024:2048], iq)
    # 循环铺排近似保 RMS (52 整周期 + 512/1024 截断 -> 相对差 < 2%)
    assert abs(C.native_rms(tiled) - C.native_rms(iq)) < 0.02 * C.native_rms(iq)


@test
def t04_rms_and_atten_ceiling():
    assert C.RF_TARGET_RMS == 2048.0
    assert C.RF_TX_ATTEN_DB_MAX == -40.0
    assert C.RF_RESIDUAL_GATE == 0.100
    assert C.RF_MAX_RECAPTURE == 3
    big = np.full(1024, 3.0 + 0j)
    assert not build_tx_payload(big)["clip_post"]
    spike = np.zeros(1024, dtype=np.complex128)
    spike[0] = 30000.0
    ev = build_tx_payload(spike)
    assert ev["clip_post"] or ev["clip_pre"]


@test
def t05_outdir_anti_overwrite():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "exists"
        out.mkdir()
        r = run_py(["export_radioml_dualsdr_tx_payload.py",
                    "--input-package", str(NPU_AB), "--out-dir", str(out)])
        assert r.returncode == 2, "anti-overwrite must exit 2"


@test
def t06_pipeline_and_judger_denominator():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        tx = td / "tx"
        r = run_py(["export_radioml_dualsdr_tx_payload.py",
                    "--input-package", str(NPU_AB), "--out-dir", str(tx)])
        assert r.returncode == 0, r.stderr
        # 可追溯: 每帧 TX payload 有 SHA 且计入 SHA256SUMS
        assert (tx / "tx_manifest.tsv").exists()
        assert (tx / "SHA256SUMS.txt").exists()
        assert (tx / "1.i16").stat().st_size == 2 * C.RF_PAYLOAD_COMPLEX * 2

        dig = td / "dig"
        r = run_py(["digital_roundtrip_radioml_dualsdr.py",
                    "--input-package", str(NPU_AB), "--out-dir", str(dig)])
        assert r.returncode == 0, r.stderr
        assert (dig / "1.recovered.bin").stat().st_size == 8192

        # 合成板端结果 (读真实 label; 构造 4 种口径)
        frames = parse_npu_ab_manifest(NPU_AB / "manifest.tsv")
        by_id = {f["selection_id"]: f for f in frames}
        board_tsv = td / "board.tsv"
        with open(board_tsv, "w", encoding="utf-8") as f:
            f.write("selection_id\thdf5_row_index\traw24_class\tdataset_snr_db\tgated\t"
                    "board_pred\tfinite\tresidual\tcorr\tcoarse_cfo_hz\tfine_cfo_hz\t"
                    "total_cfo_hz\tfractional_timing_samples\tclip\tcapture_attempts\t"
                    "gate_reject\thard_invalid\ttx_stop_ok\trx_restore_ok\n")
            for sid in sorted(by_id):
                fr = by_id[sid]
                if sid == 1:
                    # 门拒, 恢复有效 -> 可强制 (residual 0.15)
                    row = [sid, fr["hdf5_row_index"], fr["raw24_class"], fr["dataset_snr_db"],
                           0, -1, 0, 0.15, 0.990, 0, 0, 0, 0, 0, 3, 1, 0, 1, 1]
                elif sid == 2:
                    # 门拒 + hard_invalid -> 绝不强制
                    row = [sid, fr["hdf5_row_index"], fr["raw24_class"], fr["dataset_snr_db"],
                           0, -1, 0, 0.30, 0.500, 0, 0, 0, 0, 3, 1, 1, 1, 1, 1]
                elif sid == 3:
                    # 门内, 错误
                    row = [sid, fr["hdf5_row_index"], fr["raw24_class"], fr["dataset_snr_db"],
                           1, (fr["raw24_class"] + 1) % 24, 1, 0.06, 0.998, 0, 0, 0, 0, 0, 1, 0, 0, 1, 1]
                else:
                    # 门内, 正确
                    row = [sid, fr["hdf5_row_index"], fr["raw24_class"], fr["dataset_snr_db"],
                           1, fr["raw24_class"], 1, 0.05, 0.999, 0, 0, 0, 0, 0, 1, 0, 0, 1, 1]
                f.write("\t".join(str(v) for v in row) + "\n")

        jd = td / "judge"
        r = run_py(["judge_radioml_dualsdr.py", "--input-package", str(NPU_AB),
                    "--digital", str(dig / "digital_roundtrip.tsv"),
                    "--board", str(board_tsv), "--out-dir", str(jd)])
        assert r.returncode == 0, r.stderr
        s = json.loads((jd / "judge_summary.json").read_text())
        assert s["coverage"]["C"] == 480, "all 480 board frames in denominator"
        # 门内 = 478 (除帧1,2), 门内正确 = 477 (帧3 错) -> e2e = 477/480
        assert abs(s["accuracy"]["C_end_to_end_gate_reject_is_fail"] - 477/480) < 1e-9
        assert abs(s["accuracy"]["C_gated"] - 477/478) < 1e-9
        # 可强制 = 门拒且非 hard_invalid = 仅帧1
        assert s["accuracy"]["C_gate_reject_forceable_count"] == 1
        # arm A 参考 = Host BF16 419/480
        assert abs(s["accuracy"]["A_host_bf16_reference"] - 419/480) < 1e-9


@test
def t07_digital_nonidentical_not_misattributed():
    with tempfile.TemporaryDirectory() as td:
        dig = Path(td) / "dig"
        r = run_py(["digital_roundtrip_radioml_dualsdr.py",
                    "--input-package", str(NPU_AB), "--out-dir", str(dig)])
        assert r.returncode == 0, r.stderr
        s = json.loads((dig / "digital_roundtrip_summary.json").read_text())
        assert s["byte_identical"] == 0, "CI16 量化使数字回环非 byte-identical"
        assert s["corr_min"] > 0.999, "但相关极近 1 (量化噪声)"
        assert "DIGITAL_IDENTITY_ASSUMED" in s["recovery_assumption"]
        assert "待板端验证" in s["recovery_assumption"]


@test
def t08_sha_mismatch_rejected():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        pkg = td / "pkg"
        shutil.copytree(NPU_AB, pkg)  # 480 .bin + manifest + SHA256SUMS
        (pkg / "1.bin").write_bytes(b"\x00" * 8192)
        r = run_py(["export_radioml_dualsdr_tx_payload.py",
                    "--input-package", str(pkg), "--out-dir", str(td / "tx")])
        assert r.returncode != 0, "SHA mismatch must fail closed"


@test
def t09_lround_and_burst_byte_exactness():
    # lround = half-away-from-zero (NOT numpy.rint half-to-even)
    assert int(C.lround(np.array([0.5, -0.5, 2.5, -2.5, 1.5, -1.5]))[0]) == 1
    assert int(C.lround(np.array([-0.5]))[0]) == -1
    assert int(C.lround(np.array([2.5]))[0]) == 3
    assert int(C.lround(np.array([-2.5]))[0]) == -3
    # quantize_ci16 必须保虚部 (复输入逐分量取整, 不丢弃 Q)
    q = C.quantize_ci16(np.array([0.0 + 3.0j]), 1.0)
    assert int(q[0]) == 0 and int(q[1]) == 3, "Q must not be discarded"
    # burst 长度 + 前导/尾幅度上界 + payload 无关包装块 SHA 稳定
    burst = B.build_burst(np.zeros(B.K_PAYLOAD_COMPLEX * 2, dtype="<i2"))
    assert burst.size == 119808
    assert int(np.abs(B.preamble_int16()).max()) <= 2048
    assert int(np.abs(B.tail_int16()).max()) <= 2048
    w = B.wrapper_sha256s()
    assert w["preamble_sha256"] == "d4b4bb3af9ad57836f4de7dfd9046898983c66f949d33aad35ed8dc434ccc97f"
    assert w["tail_sha256"] == "ccddabe154b62a4cbae7d628f410d89ef9bfd54ebbaf79d83139417a36666a8e"


@test
def t10_loader_contract_constants():
    """arm C loader 的冻结契约常量必须与导出脚本逐字一致。"""
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
def t11_runner_red_line_source_audit():
    """arm C runner 红线源码审计 (双 SDR RX-only, 无本地 TX)。"""
    src = RUNNER.read_text(encoding="utf-8")
    # 双 SDR 控制通道 (板端 RX-only, 无 TX API; PC 拥有 TX)
    assert "--tx-control=tcp://" in src
    assert "send_hello" in src and "send_prepare" in src and "send_start" in src
    assert "run_rx_negative_control" in src
    # 生产恢复
    assert "recover_payload_with_coarse_cfo" in src
    # RX 手动增益默认 35 dB
    assert 'board::opt_d(argc, argv, "--rx-gain", 35.0)' in src
    # RX BW 默认 18 MHz
    assert 'board::opt_u64(argc, argv, "--rx-bw", 18000000ULL)' in src
    # input-kind fail-closed
    assert "--input-kind=radioml-original-dualsdr-ab-2p56m" in src
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
def t12_board_producer_wiring():
    """arm C producer 接线: gate9_phase.hpp phase + board_gate9 include/wrapper/dispatch。"""
    phase = GATE9_PHASE.read_text(encoding="utf-8")
    assert 'p == "radioml-original-dualsdr-ab-24class-bf16-fix10"' in phase

    bg = BOARD_GATE9.read_text(encoding="utf-8")
    assert '#include "radioml_dualsdr_ab_runner.hpp"' in bg
    assert "int run_radioml_original_dualsdr_ab(" in bg
    assert 'phase == "radioml-original-dualsdr-ab-24class-bf16-fix10"' in bg
    assert '"radioml-original-dualsdr-ab-24class-bf16-fix10)"' in bg
    assert "rmldsab::DualsdrAbRunReport" in bg
    assert "rmldsab::run_radioml_original_dualsdr_ab" in bg
    assert "emit_frame_rml24" in bg
    assert "device_not_found" in bg
    assert "final_gate_pass" in bg
    # phase 与 singlesdr 的 phase 共存 (同一 gate9_phase.hpp 同时列出两者)
    assert 'p == "radioml-original-npu-ab-24class-bf16-fix10"' in phase


@test
def t13_run_script_source_audit():
    """full480 + short24 run 脚本: 双 SDR 参数 + 24 类模型 + 显式 --rx-gain=35。"""
    full = RUN_SH_FULL.read_text(encoding="utf-8")
    short = RUN_SH_SHORT.read_text(encoding="utf-8")
    for src, mode in ((full, "full480"), (short, "short24")):
        assert "radioml-original-dualsdr-ab-24class-bf16-fix10" in src
        assert "--mode=%s" % mode in src
        # 双 SDR: 板端是控制通道 CLIENT, 必须显式 --tx-control + --rx-uri
        assert "--tx-control=\"$TX_CONTROL\"" in src
        assert "--rx-uri=\"$RX_URI\"" in src
        # 显式 --rx-gain=35 (覆盖 run_gate9_rml23.sh 默认 --rx-gain=10)
        assert 'RX_GAIN_DB=35.0' in src
        assert "--rx-gain=\"$RX_GAIN_DB\"" in src
        # RX BW 18 MHz + input-kind + rf-path
        assert 'RX_BW=18000000' in src
        assert "--rx-bw=\"$RX_BW\"" in src
        assert "--input-kind=\"$INPUT_KIND\"" in src
        assert "--rf-path=\"$RF_PATH\"" in src
        assert 'RF_PATH="direct-cable"' in src
        assert 'INPUT_KIND="radioml-original-dualsdr-ab-2p56m"' in src
        # 24 类模型 + SHA
        assert "--model-json=\"$MODEL_JSON\"" in src and "--model-raw=\"$MODEL_RAW\"" in src
        assert 'MODEL_JSON_SHA="28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"' in src
        assert 'MODEL_RAW_SHA="c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"' in src
        # 输入包 = tx payload 包 (tx_manifest + route_d2_rf_manifest), 非 npu-ab1 manifest
        assert "tx_manifest.tsv" in src
        assert "route_d2_rf_manifest.tsv" in src


@test
def t14_gate_reject_raw_capture_and_diag_saved():
    """门拒 + hard-invalid 样本同样落盘原始捕获 + 恢复诊断 (不只在过门分支)。

    runner 必须在过门分支之前无条件写 <sid>.raw.i16 (原始捕获) 与 <sid>.diag.json
    (恢复诊断), 使 gate-reject/hard-invalid 帧也落盘, 离线可复查而非重新采集。
    gate-reject/hard-invalid 仍计入分母, 绝不剔除 (t06 已证)。
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
def t15_result_rows_survive_capture_try_scope():
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
    print("RADIOML_DUALSDR_AB1_SELFTEST %d/%d passed" % (passed, len(TESTS)))
    sys.exit(0 if passed == len(TESTS) else 1)


if __name__ == "__main__":
    main()
