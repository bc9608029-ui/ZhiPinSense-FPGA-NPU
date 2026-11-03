#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_radioml_dc_dualsdr.py -- 主机测试 (fix10class24-original-radioml-dc-ab1,
双 SDR 部分)。

g++ 在本 Windows 主机不可用, 板端 C++ 在 aarch64 编译; 故本测试为 Python-only, 覆盖
双 SDR 部分的最小主机不变量 (纯离线只读, 不碰板/不发射/不训练):

  1. 480 帧主键唯一 + 身份 (与 npu-ab1 逐字节一致)。
  2. short24 固定选取 (每类 1 帧 @30 dB, 最小 selection_id)。
  3. DC 适配确定性 + 类无关 + 去 DC 后 AC 循环铺排近似保 RMS。
  4. DC 数字理想往返还原原始 IQ (corr ~ 1, 量化误差小, 无裁剪/非有限)。
  5. dc-transport 22 列清单导出: 表头逐字 == 契约; DC 参数与逐帧复算一致。
  6. dualsdr loader 契约常量 + DC 参数源码审计 (共享头引用, 单一实现)。
  7. dualsdr runner 红线源码审计 (--adaptation 门 + input_kind 派生 + DC 分支 +
     direct 分支逐字不变 + RX-only + HELLO manifest_sha256 + 窗口位置)。
  8. 共享 DC 头 (radioml_dc_adapt.hpp) 单一实现审计 (单/双 runner 均 include)。
  9. 冻结模型 SHA + 契约文件存在 + 契约 JSON token。
  10. PC-TX producer DC-aware 审计 (input_kind 派生 / direct·dc 24 列映射 / route_d2
      表头 / TX -40 上限) + --self-test 子进程 PASS。
  11. 集成 gate9_phase + board_gate9 三相位共存 (npu + dualsdr + singlesdr) 审计。
  12. 数字验证 (24 帧) 预测一致: original 复现 arm A 24/24、direct/dc 全对、dc 与
      direct 24/24 一致 (读已跑出的 summary, 若缺失则报 FAIL)。
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
import radioml_dc_adapt as DC  # noqa: E402
from export_radioml_dualsdr_tx_payload import (  # noqa: E402
    parse_npu_ab_manifest, TX_MANIFEST_HEADER)
from export_radioml_dc_tx_payload import DC_EXTRA_HEADER  # noqa: E402

NPU_AB = Path(r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work"
              r"\sdr_rml24_fix10class24_original_radioml_npu_ab1\input_package")
DUALSDR_TX = Path(r"F:\嵌赛\fix10class24_original_radioml_dualsdr_ab1_work"
                  r"\results\tx_payload")
DIGITAL_SUMMARY = ROOT / "results" / "digital_roundtrip_dc" / \
                  "digital_roundtrip_dc_summary.json"

RUNNER = ROOT / "board_package" / "radioml_dualsdr_ab_runner.hpp"
LOADER = ROOT / "board_package" / "radioml_dualsdr_ab_loader.hpp"
SINGLE_RUNNER = ROOT / "board_package" / "radioml_singlesdr_ab_runner.hpp"
SINGLE_LOADER = ROOT / "board_package" / "radioml_singlesdr_ab_loader.hpp"
DC_HPP = ROOT / "board_package" / "radioml_dc_adapt.hpp"
GATE9_PHASE = ROOT / "board_package" / "gate9_phase.hpp"
BOARD_GATE9 = ROOT / "board_package" / "board_gate9_full_chain_rml23.cpp"
PRODUCER = SCRIPTS / "pc_tx_radioml_dualsdr.py"
CONTRACT_MD = ROOT / "contract" / "dc_transport_adaptation_contract.md"
CONTRACT_JSON = ROOT / "contract" / "dc_transport_adaptation_contract.json"

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


def run_py(args, cwd=None):
    return subprocess.run([sys.executable, "-I", str(SCRIPTS / args[0])] + args[1:],
                          capture_output=True, text=True, cwd=cwd)


@test
def t01_real480_identity_unique():
    frames = parse_npu_ab_manifest(NPU_AB / "manifest.tsv")
    assert len(frames) == 480
    assert len({f["hdf5_row_index"] for f in frames}) == 480
    assert len({f["input_file"] for f in frames}) == 480
    assert len({f["model_input_sha256"] for f in frames}) == 480
    assert all(0 <= f["raw24_class"] < 24 for f in frames)
    assert all(f["dataset_snr_db"] in (0, 10, 20, 30) for f in frames)


@test
def t02_short24_selection():
    frames = parse_npu_ab_manifest(NPU_AB / "manifest.tsv")
    sel = C.short24_selection(frames)
    assert len(sel) == 24
    assert len({f["raw24_class"] for f in sel}) == 24
    assert all(f["dataset_snr_db"] == 30 for f in sel)


@test
def t03_dc_adaptation_deterministic_class_agnostic():
    rng = np.random.default_rng(11)
    iq = rng.standard_normal(1024) + 1j * rng.standard_normal(1024)
    fwd1 = DC.adapt_forward(iq)
    fwd2 = DC.adapt_forward(iq)
    assert np.array_equal(fwd1["payload_i16"], fwd2["payload_i16"])
    ac = iq - fwd1["dc"]
    assert abs(np.mean(ac.real)) < 1e-12 and abs(np.mean(ac.imag)) < 1e-12
    tiled = C.cyclic_tile_1024_to_payload(ac)
    assert tiled.size == C.RF_PAYLOAD_COMPLEX
    assert np.allclose(tiled[:1024], ac)
    assert abs(C.native_rms(tiled) - fwd1["ac_rms"]) < 0.02 * fwd1["ac_rms"]
    assert abs(fwd1["tx_scale"] - C.RF_TARGET_RMS / fwd1["ac_rms"]) < 1e-12
    assert abs(fwd1["inverse_scale"] - fwd1["ac_rms"] / C.RF_TARGET_RMS) < 1e-12
    assert fwd1["clip_pre"] == 0 and fwd1["clip_post"] == 0


@test
def t04_dc_ideal_roundtrip_recovers_original():
    frames = C.short24_selection(parse_npu_ab_manifest(NPU_AB / "manifest.tsv"))
    for fr in frames:
        iq = C.load_tensor_2x1024(NPU_AB / fr["input_file"])
        rec, fwd = DC.dc_ideal_roundtrip(iq)
        corr = C.complex_corr(iq, rec)
        nmse = C.complex_nmse(iq, rec)
        assert np.all(np.isfinite(rec)), "non-finite recovered for %d" % fr["selection_id"]
        assert corr > 0.999999, "dc roundtrip corr too low: %r" % corr
        assert nmse < 1e-6, "dc roundtrip nmse too high: %r" % nmse
        assert fwd["clip_pre"] == 0 and fwd["clip_post"] == 0


@test
def t05_dc_manifest_22col_and_params():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "dc_tx"
        r = run_py(["export_radioml_dc_tx_payload.py",
                    "--input-package", str(NPU_AB), "--out-dir", str(out)])
        assert r.returncode == 0, r.stderr
        assert "RADIOML_DC_TX_PAYLOAD_DONE" in r.stdout
        manifest = (out / "tx_manifest.tsv").read_text(encoding="utf-8")
        lines = manifest.rstrip("\n").split("\n")
        header = lines[0].split("\t")
        assert header == TX_MANIFEST_HEADER + DC_EXTRA_HEADER, "22-col header mismatch"
        assert len(lines) == 481, "480 data rows + header"
        frames = parse_npu_ab_manifest(NPU_AB / "manifest.tsv")
        by_id = {f["selection_id"]: f for f in frames}
        for ln in lines[1:]:
            f = ln.split("\t")
            assert len(f) == 22
            sid = int(f[0])
            iq = C.load_tensor_2x1024(NPU_AB / by_id[sid]["input_file"])
            dc_i = float(f[18]); dc_q = float(f[19])
            ac_rms = float(f[20]); inv = float(f[21])
            assert abs(dc_i - np.mean(iq.real)) < 1e-9
            assert abs(dc_q - np.mean(iq.imag)) < 1e-9
            assert abs(ac_rms - C.native_rms(iq - complex(dc_i, dc_q))) < 1e-9
            assert abs(inv - ac_rms / C.RF_TARGET_RMS) < 1e-8
            assert f[17] == DC.ADAPTATION_DC_TRANSPORT
            assert [f[i] for i in range(0, 8)] == [
                str(by_id[sid]["selection_id"]), str(by_id[sid]["hdf5_row_index"]),
                str(by_id[sid]["raw24_class"]), by_id[sid]["modulation"],
                str(by_id[sid]["dataset_snr_db"]), by_id[sid]["input_file"],
                by_id[sid]["model_input_sha256"], str(by_id[sid]["host_pred"])]
            assert C.sha256_bytes((out / f[8]).read_bytes()) == f[9]


@test
def t06_dc_payload_differs_from_direct():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "dc_tx"
        r = run_py(["export_radioml_dc_tx_payload.py",
                    "--input-package", str(NPU_AB), "--out-dir", str(out)])
        assert r.returncode == 0, r.stderr
        frames = C.short24_selection(parse_npu_ab_manifest(NPU_AB / "manifest.tsv"))
        for fr in frames:
            dc_i16 = (out / ("%d.i16" % fr["selection_id"])).read_bytes()
            direct_i16 = (DUALSDR_TX / ("%d.i16" % fr["selection_id"])).read_bytes()
            assert dc_i16 != direct_i16, \
                "dc payload unexpectedly identical to direct at %d" % fr["selection_id"]


@test
def t07_dualsdr_loader_contract_and_dc_params_source_audit():
    src = LOADER.read_text(encoding="utf-8")
    assert "kFrameCount = 480" in src
    assert "kPayloadComplex = 53760" in src
    assert 'radioml_dc_adapt.hpp' in src
    assert "rml24dc::is_dc_transport" in src
    assert "rml24dc::dc_extra_header" in src
    assert "rml24dc::valid_adaptation" in src
    assert "rml24dc::kAdaptationDirect" in src
    for col in TX_MANIFEST_HEADER:
        assert col in src, "loader missing column %s" % col
    assert "dc_i" in src and "dc_q" in src and "ac_rms" in src and "inverse_scale" in src
    assert "manifest_header_line_dc" in src
    assert "parse_finite_double" in src
    assert "parse_positive_double" in src
    assert "input SHA" in src
    assert "never to class" in src
    assert "fr.dc.dc_i" in src and "fr.dc.dc_q" in src
    assert "fr.dc.ac_rms" in src and "fr.dc.inverse_scale" in src
    assert "is_dc ? 22 : 18" in src
    assert "fr.adaptation != adaptation" in src
    assert "load_tx_manifest" in src


@test
def t08_dualsdr_runner_red_line_source_audit():
    src = RUNNER.read_text(encoding="utf-8")
    # --adaptation 门 (direct|dc-transport, fail-closed)
    assert 'board::get_opt(argc, argv, "--adaptation", "direct")' in src
    assert 'rml24dc::kAdaptationDirect()' in src
    assert 'rml24dc::kAdaptationDcTransport()' in src
    # input_kind 由 --adaptation 派生 (双端显式适配身份)
    assert "direct_input_kind" in src
    assert '"-dc-transport"' in src
    assert "rml24dc::is_dc_transport(rep.adaptation)" in src
    assert "sess.input_kind = rep.input_kind" in src
    # 共享头 reconstruct_dc_window 分支 + direct 分支逐字不变
    assert "rml24dc::reconstruct_dc_window(" in src
    assert "rml24dc::is_dc_transport(fr.adaptation)" in src
    assert "payload[k].real() * fr.unscale" in src
    assert "payload[k].imag() * fr.unscale" in src
    # RX-only 双 SDR: 控制通道 HELLO + manifest_sha256 + 生产恢复
    assert "recover_payload_with_coarse_cfo" in src
    assert "send_hello" in src and "recv_hello_ack" in src
    assert "d2_manifest_path" in src
    assert "load_tx_manifest(rep.input_dir" in src
    # 红绳: RX 35 dB / 2.56M / direct-cable / out-dir 不覆盖 / 末次重捕 / 不强制分类
    assert 'board::opt_d(argc, argv, "--rx-gain", 35.0)' in src
    assert "sample_rate != 2560000LL" in src
    assert 'rf_path != "direct-cable"' in src
    assert "--out-dir already exists" in src
    assert "should_retry_payload_training_capture" in src
    assert "board_pred = finite ? raw_top : -1;" in src


@test
def t09_shared_dc_header_single_impl():
    src = DC_HPP.read_text(encoding="utf-8")
    assert "kAdaptationDirect" in src and "kAdaptationDcTransport" in src
    assert "valid_adaptation" in src and "dc_extra_header" in src
    assert "struct DcParams" in src
    assert "reconstruct_dc_window" in src
    assert "p.inverse_scale" in src
    assert "p.dc_i" in src and "p.dc_q" in src
    assert 'radioml_dc_adapt.hpp' in RUNNER.read_text(encoding="utf-8")
    assert 'radioml_dc_adapt.hpp' in SINGLE_RUNNER.read_text(encoding="utf-8")
    assert 'radioml_dc_adapt.hpp' in LOADER.read_text(encoding="utf-8")
    assert 'radioml_dc_adapt.hpp' in SINGLE_LOADER.read_text(encoding="utf-8")
    assert DC.ADAPTATION_DIRECT in src
    assert DC.ADAPTATION_DC_TRANSPORT in src


@test
def t10_frozen_model_identity_and_contract_files():
    assert C.FROZEN_MODEL_JSON_SHA == \
        "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
    assert C.FROZEN_MODEL_RAW_SHA == \
        "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
    assert C.FROZEN_CKPT_SHA == \
        "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"
    assert CONTRACT_MD.is_file(), "dc contract md missing"
    assert CONTRACT_JSON.is_file(), "dc contract json missing"
    j = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    assert j["token"] == \
        "M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-DC-AB1-DC-TRANSPORT-ADAPTATION-CONTRACT"
    assert j["adaptation_tags"]["direct"] == DC.ADAPTATION_DIRECT
    assert j["adaptation_tags"]["dc_transport"] == DC.ADAPTATION_DC_TRANSPORT


@test
def t11_producer_dc_aware_source_and_self_test():
    src = PRODUCER.read_text(encoding="utf-8")
    # input_kind 派生 + 冻结串
    assert "DIRECT_INPUT_KIND = \"radioml-original-dualsdr-ab-2p56m\"" in src
    assert "DC_INPUT_KIND = DIRECT_INPUT_KIND + \"-dc-transport\"" in src
    assert "def derive_input_kind" in src
    assert "def parse_tx_manifest" in src
    assert "def map_row_to_route_d2" in src
    assert "def build_frozen_dir" in src
    # direct/dc 24 列映射: DC 列 provenance
    assert "original_dc_i" in src and "original_dc_q" in src
    assert "ac_rms" in src and "rec_scale" in src
    assert "inverse_scale" in src
    # route_d2 表头 24 列 + 引擎只读列
    assert 'len(ROUTE_D2_MANIFEST_HEADER) == 24' in src
    assert "SERVICE_READ_COLS" in src
    # TX 硬上限 -40 dB (服务/producer 侧, board RX-only 无 TX)
    assert "RF_TX_ATTEN_DB = -40.0" in src
    assert "--tx-atten" in src
    assert "--adaptation" in src
    # 实际跑 producer --self-test (子进程, 无 SDR)
    r = run_py(["pc_tx_radioml_dualsdr.py", "--self-test"])
    assert r.returncode == 0, "producer --self-test failed:\n%s\n%s" % (r.stdout, r.stderr)
    assert "RADIOML_DUALSDR_PC_TX_SELF_TEST PASS" in r.stdout


@test
def t12_integrated_gate9_three_phase_audit():
    phase = GATE9_PHASE.read_text(encoding="utf-8")
    assert "radioml-original-npu-ab-24class-bf16-fix10" in phase
    assert "radioml-original-dualsdr-ab-24class-bf16-fix10" in phase
    assert "radioml-original-singlesdr-ab-24class-bf16-fix10" in phase
    gate9 = BOARD_GATE9.read_text(encoding="utf-8")
    assert "radioml_dualsdr_ab_runner.hpp" in gate9
    assert "radioml_singlesdr_ab_runner.hpp" in gate9
    assert "run_radioml_original_dualsdr_ab" in gate9
    assert "run_radioml_original_singlesdr_ab" in gate9


@test
def t13_digital_verification_agreement():
    assert DIGITAL_SUMMARY.is_file(), \
        "digital_roundtrip_dc_summary.json missing (run scripts/digital_roundtrip_radioml_dc.py)"
    s = json.loads(DIGITAL_SUMMARY.read_text(encoding="utf-8"))
    pa = s["prediction_agreement"]
    assert pa["original_reproduces_arm_a_host_pred"] == 24
    assert pa["direct_correct"] == "24/24"
    assert pa["dc_correct"] == "24/24"
    assert pa["direct_agrees_original"] == "24/24"
    assert pa["dc_agrees_original"] == "24/24"
    assert pa["dc_agrees_direct"] == "24/24"
    assert s["clip_pre"] == 0 and s["clip_post"] == 0
    assert s["non_finite"] == 0
    assert s["corr_direct_min"] > 0.999999
    assert s["corr_dc_min"] > 0.999999


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
    print("RADIOML_DC_DUALSDR_SELFTEST %d/%d passed" % (passed, len(TESTS)))
    sys.exit(0 if passed == len(TESTS) else 1)


if __name__ == "__main__":
    main()
