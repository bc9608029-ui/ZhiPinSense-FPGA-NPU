#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pc_tx_radioml_dualsdr.py -- PC 侧 TX 启动器/适配器 (DC-aware)
(fix10class24-original-radioml-dc-ab1, 双 SDR 部分; 纯主机侧; 不发射、不训练、不碰板)。

薄封装, 复用现有 fix10prep2 的 PC TX 服务
(host_tools/pc_tx_sdr_fix10.py + fix10_tx_protocol.py + build_burst_cli)。
Python 绝不重实现帧数学 (lround/LCG/Zadoff-Chu 是红线); 本脚本只做主机侧的事:

  1. build-frozen-dir: 把本任务的 tx payload 目录 (18 列 direct 或 22 列 dc-transport
     tx_manifest.tsv + <sid>.i16) 转换为现有 PC TX 服务期望的 24 列
     route_d2_rf_manifest.tsv。只在该目录原地新增一个 manifest 文件, 不复制/改写任何
     .i16。
  2. launch: 用 --frozen-dir 指向该目录, 以 --rf-path direct-cable + --tx-atten -40
     + --tx-bw 18M + --sample-rate 2.56M + --center 2.4G + --rf-tx-target-rms 2048
     启动现有服务 (exec, 不重复实现其 SDR 逻辑)。

DC 适配 (fix10class24-original-radioml-dc-ab1) 的增量:
  * --adaptation=direct|dc-transport 显式选择适配路径; input_kind 由 adaptation 派生
    (direct = "radioml-original-dualsdr-ab-2p56m"; dc-transport = 该串 + "-dc-transport"),
    与板端 runner 的派生规则逐字一致。双端 (PC TX 服务 --input-kind 与板端 HELLO
    input_kind) 不一致时, 现有服务在 HELLO 阶段立即 fail-closed 拒绝 —— 不靠事后发现。
  * direct 路径的 24 列映射逐字节不变 (original_dc_i/original_dc_q=0, ac_rms=native_rms,
    rec_scale=unscale); dc-transport 路径把 4 列 DC 参数 (dc_i/dc_q/ac_rms/inverse_scale)
    诚实写入 original_dc_i/original_dc_q/ac_rms/rec_scale 作为 provenance。
  * PC TX 引擎只读 source_index/modulation/split_role/complex_count/sample_rate/
    original_sha256/quantized_sha256/file_name (判定用 file_name + quantized_sha256 +
    complex_count), **不消费 DC 列** —— DC 的 .i16 已是纯 AC 分量, 发射行为与 direct 相同。

诚实边界 (红线不越):
  * 板端 producer phase `radioml-original-dualsdr-ab-24class-bf16-fix10` 属集成 (本 dc-ab1
    集成 PATCH 已含 3-phase gate9_phase + board_gate9); 本启动器是主机侧预演, 真实双 SDR
    会话由板端发起 (板端是控制通道 CLIENT, PC 是 SERVER)。
  * 24 列 manifest 中与 D2 路由相关的占位列 (deployed23_class=-1 /
    edge_policy=cyclic_tile_1024 / recovered_tensor_*=PENDING) 仅为满足现有服务
    ManifestIndex 的列数校验, 不消费标签/SNR。

用法 (Windows, radioconda python -I):
    python -I scripts/pc_tx_radioml_dualsdr.py build-frozen-dir \
        --tx-payload results/tx_payload --adaptation=direct
    python -I scripts/pc_tx_radioml_dualsdr.py build-frozen-dir \
        --tx-payload <dc tx payload dir> --adaptation=dc-transport
    python -I scripts/pc_tx_radioml_dualsdr.py launch \
        --tx-payload results/tx_payload --adaptation=direct --tx-uri "<PC_TX_URI>"
    python -I scripts/pc_tx_radioml_dualsdr.py --self-test
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_dc_adapt as DC  # noqa: E402

# ---------------------------------------------------------------------------
# 冻结常量 (继承自 npu-ab1 / fix10prep2; 不在本脚本重新推导)
# ---------------------------------------------------------------------------
FROZEN_MODEL_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

RF_PAYLOAD_COMPLEX = 53760            # kPayloadComplex (生产冻结)
RF_SAMPLE_RATE = 2560000              # 2.56 Msps
RF_TARGET_RMS = 2048.0                # --rf-tx-target-rms 冻结
RF_CENTER_HZ = 2400000000
RF_TX_BW_HZ = 18000000
RF_TX_ATTEN_DB = -40.0                # 硬上限 (<= -40)
RF_GUARD_COMPLEX = 2048               # kGuardComplex (burst 布局, 非 D2 数字回环 guard)

# 文档化默认 input_kind (direct)。dc-transport 追加 "-dc-transport" 后缀, 与板端 runner
# 派生规则逐字一致。
DIRECT_INPUT_KIND = "radioml-original-dualsdr-ab-2p56m"
DC_INPUT_KIND = DIRECT_INPUT_KIND + "-dc-transport"

# 板端 producer phase 名 (与 contract §5 / 板测手册 §6 一致)。
PHASE_NAME = "radioml-original-dualsdr-ab-24class-bf16-fix10"

# 本任务 TX 派生 manifest 表头 (18 列; 与 export_radioml_dualsdr_tx_payload.py 一致)
TX_MANIFEST_HEADER = [
    "selection_id", "hdf5_row_index", "raw24_class", "modulation",
    "dataset_snr_db", "input_file", "model_input_sha256", "host_pred",
    "tx_payload_file", "tx_payload_sha256", "native_rms", "tx_scale",
    "unscale", "peak_pre", "peak_post", "clip_pre", "clip_post",
    "adaptation",
]
# dc-transport 追加 4 列 (dc_i/dc_q/ac_rms/inverse_scale)。
DC_EXTRA_HEADER = ["dc_i", "dc_q", "ac_rms", "inverse_scale"]

# 现有 PC TX 服务期望的 24 列 route_d2_rf_manifest.tsv 表头 (逐字)
ROUTE_D2_MANIFEST_HEADER = [
    "sample_index", "source_index", "raw24_class", "deployed23_class",
    "modulation", "snr_db", "split_role", "global_K", "original_dc_i",
    "original_dc_q", "ac_rms", "rec_scale", "complex_count", "sample_rate",
    "tx_rms", "tx_peak", "clip_count", "edge_policy", "guard",
    "original_sha256", "quantized_sha256", "recovered_tensor_sha256",
    "quantized_file", "recovered_tensor_file",
]
assert len(ROUTE_D2_MANIFEST_HEADER) == 24

# 现有 PC TX 服务只读这些列 (ManifestIndex._load 的子集); 其余为占位/元数据。
SERVICE_READ_COLS = {
    "source_index": 1, "modulation": 4, "split_role": 6, "complex_count": 12,
    "sample_rate": 13, "original_sha256": 19, "quantized_sha256": 20,
    "file_name": 22,
}

# CLI adaptation 短名 -> 冻结 tag (radioml_dc_adapt.py 单一权威)。
CLI_ADAPTATION_TO_TAG = {
    "direct": DC.ADAPTATION_DIRECT,
    "dc-transport": DC.ADAPTATION_DC_TRANSPORT,
}


def valid_adaptation_cli(a: str) -> bool:
    return a in CLI_ADAPTATION_TO_TAG


def adaptation_tag(adaptation_cli: str) -> str:
    return CLI_ADAPTATION_TO_TAG[adaptation_cli]


def derive_input_kind(adaptation_cli: str) -> str:
    return DC_INPUT_KIND if adaptation_cli == "dc-transport" else DIRECT_INPUT_KIND


def parse_tx_manifest(path: Path, adaptation_cli: str):
    """读 18 列 (direct) 或 22 列 (dc-transport) tx_manifest.tsv, fail-closed。

    返回 list[dict]; dc 行额外带 dc_i/dc_q/ac_rms/inverse_scale 键。
    逐字节校验表头 + 列数 + 主键唯一 + 每帧 adaptation 列 == 冻结 tag。
    """
    tag = adaptation_tag(adaptation_cli)
    is_dc = adaptation_cli == "dc-transport"
    expected_header = TX_MANIFEST_HEADER + (DC_EXTRA_HEADER if is_dc else [])
    expected_cols = len(expected_header)

    lines = path.read_text(encoding="utf-8").rstrip("\n").split("\n")
    header = lines[0].rstrip("\r").split("\t")
    assert header == expected_header, \
        "tx_manifest.tsv header mismatch for --adaptation=%s (expected %d-col header)" % (
            adaptation_cli, expected_cols)
    rows = []
    seen = set()
    for ln in lines[1:]:
        ln = ln.rstrip("\r")
        if not ln.strip():
            continue
        f = ln.split("\t")
        assert len(f) == expected_cols, \
            "tx_manifest.tsv line not %d columns for --adaptation=%s: %r" % (
                expected_cols, adaptation_cli, ln)
        sid = int(f[0])
        assert sid not in seen, "duplicate selection_id %d" % sid
        seen.add(sid)
        row = {
            "selection_id": sid,
            "hdf5_row_index": int(f[1]),
            "raw24_class": int(f[2]),
            "modulation": f[3],
            "dataset_snr_db": int(f[4]),
            "input_file": f[5],
            "model_input_sha256": f[6],
            "host_pred": int(f[7]),
            "tx_payload_file": f[8],
            "tx_payload_sha256": f[9],
            "native_rms": float(f[10]),
            "tx_scale": float(f[11]),
            "unscale": float(f[12]),
            "peak_pre": float(f[13]),
            "peak_post": float(f[14]),
            "clip_pre": int(f[15]),
            "clip_post": int(f[16]),
            "adaptation": f[17],
            "is_dc": is_dc,
        }
        assert row["adaptation"] == tag, \
            "frame %d adaptation tag '%s' != --adaptation=%s tag '%s'" % (
                sid, row["adaptation"], adaptation_cli, tag)
        if is_dc:
            row["dc_i"] = float(f[18])
            row["dc_q"] = float(f[19])
            row["ac_rms"] = float(f[20])
            row["inverse_scale"] = float(f[21])
        rows.append(row)
    return rows


def map_row_to_route_d2(r: dict) -> list:
    """18 列 (direct) / 22 列 (dc) 行 -> 24 列 route_d2_rf_manifest 行 (占位列诚实标注)。

    仅 source_index/complex_count/sample_rate/quantized_sha256/file_name 被 PC TX 引擎
    用于判定; 其余列是满足 ManifestIndex 列数校验的元数据/占位, 不消费标签/SNR。

    direct: original_dc_i/original_dc_q = 0, ac_rms = native_rms, rec_scale = unscale
            (与 dualsdr-ab1 逐字节一致)。
    dc:     original_dc_i = dc_i, original_dc_q = dc_q, ac_rms = ac_rms,
            rec_scale = inverse_scale (provenance; 引擎不消费, .i16 已是纯 AC)。
    """
    dc_i = r["dc_i"] if r["is_dc"] else 0.0
    dc_q = r["dc_q"] if r["is_dc"] else 0.0
    ac_rms = r["ac_rms"] if r["is_dc"] else r["native_rms"]
    rec_scale = r["inverse_scale"] if r["is_dc"] else r["unscale"]
    # direct 的 original_dc_i/original_dc_q 用字面量 "0.0" (与 dualsdr-ab1 逐字节一致);
    # dc 用 "%.9f" 写入真实 DC 参数作为 provenance。
    dc_i_str = "0.0" if not r["is_dc"] else "%.9f" % dc_i
    dc_q_str = "0.0" if not r["is_dc"] else "%.9f" % dc_q
    return [
        str(r["selection_id"] - 1),      # 0  sample_index (0-based, 仅元数据)
        str(r["selection_id"]),          # 1  source_index = selection_id
        str(r["raw24_class"]),           # 2  raw24_class (元数据, 不消费)
        "-1",                            # 3  deployed23_class: N/A (24 类任务, 无 23 合并)
        r["modulation"],                 # 4  modulation (元数据)
        str(r["dataset_snr_db"]),        # 5  snr_db = 数据集标称 SNR (非 RX SNR)
        "holdout",                       # 6  split_role: 本测量无 calibration 子集
        "%.9f" % RF_TARGET_RMS,          # 7  global_K = 2048
        dc_i_str,                        # 8  original_dc_i (direct="0.0"; dc=dc_i)
        dc_q_str,                        # 9  original_dc_q (direct="0.0"; dc=dc_q)
        "%.9f" % ac_rms,                 # 10 ac_rms (direct=native_rms; dc=ac_rms)
        "%.9f" % rec_scale,              # 11 rec_scale (direct=unscale; dc=inverse_scale)
        str(RF_PAYLOAD_COMPLEX),         # 12 complex_count = 53760 (引擎判定)
        str(RF_SAMPLE_RATE),             # 13 sample_rate = 2.56 Msps
        "%.9f" % RF_TARGET_RMS,          # 14 tx_rms = 目标 RMS (量化到 RMS2048)
        "%.3f" % r["peak_post"],         # 15 tx_peak = .i16 峰值
        str(r["clip_pre"] or r["clip_post"]),  # 16 clip_count (export 已断言为 0)
        "cyclic_tile_1024",              # 17 edge_policy: 循环铺排适配
        str(RF_GUARD_COMPLEX),           # 18 guard = kGuardComplex 2048
        r["model_input_sha256"],         # 19 original_sha256 = [2,1024] f32 .bin SHA
        r["tx_payload_sha256"],          # 20 quantized_sha256 = <sid>.i16 SHA (引擎判定)
        "PENDING",                       # 21 recovered_tensor_sha256: 板端 RX 后才有
        r["tx_payload_file"],            # 22 quantized_file = file_name (引擎判定)
        "PENDING",                       # 23 recovered_tensor_file
    ]


def build_frozen_dir(tx_payload: Path, adaptation_cli: str,
                     out_frozen: Path | None = None) -> Path:
    """把 tx_payload 目录转成现有服务可用的 frozen dir (原地加 manifest, 不复制 .i16)。

    默认 out_frozen == tx_payload (原地), 只新增 route_d2_rf_manifest.tsv。
    """
    if not (tx_payload / "tx_manifest.tsv").exists():
        raise SystemExit("ERROR: tx_manifest.tsv not found in %s" % tx_payload)
    rows = parse_tx_manifest(tx_payload / "tx_manifest.tsv", adaptation_cli)
    target = out_frozen if out_frozen is not None else tx_payload
    target.mkdir(parents=True, exist_ok=True)

    # 逐帧校验 .i16 存在且字节数正确 (53760 复 * 2B * 2 = 215040)
    for r in rows:
        p = tx_payload / r["tx_payload_file"]
        if not p.exists():
            raise SystemExit("ERROR: missing tx payload file %s" % p)
        if p.stat().st_size != 2 * RF_PAYLOAD_COMPLEX * 2:
            raise SystemExit("ERROR: bad .i16 size for %s" % r["tx_payload_file"])

    manifest = target / "route_d2_rf_manifest.tsv"
    with open(manifest, "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(ROUTE_D2_MANIFEST_HEADER) + "\n")
        for r in rows:
            f.write("\t".join(map_row_to_route_d2(r)) + "\n")
    return manifest


def find_pc_tx_service(service_path: str | None) -> str:
    """定位现有 pc_tx_sdr_fix10.py (默认指向 npu-ab1 只读参照树的 host_tools)。"""
    if service_path:
        p = Path(service_path)
    else:
        p = Path(
            r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work"
            r"\sdr_rml24_fix10class24_original_radioml_npu_ab1"
            r"\host_tools\pc_tx_sdr_fix10.py")
    if not p.exists():
        raise SystemExit("ERROR: pc_tx_sdr_fix10.py not found at %s (pass --pc-tx-service)" % p)
    return str(p)


def cmd_build_frozen_dir(args):
    manifest = build_frozen_dir(Path(args.tx_payload), args.adaptation,
                                Path(args.out_frozen) if args.out_frozen else None)
    print("RADIOML_DUALSDR_FROZEN_DIR adaptation=%s input_kind=%s manifest=%s columns=%d" %
          (args.adaptation, derive_input_kind(args.adaptation), manifest,
           len(ROUTE_D2_MANIFEST_HEADER)))
    print("RADIOML_DUALSDR_FROZEN_DIR_DONE")


def cmd_launch(args):
    service = find_pc_tx_service(args.pc_tx_service)
    if not args.tx_uri:
        raise SystemExit("ERROR: --tx-uri=<libiio URI of PC TX SDR> is required to launch")
    manifest = build_frozen_dir(Path(args.tx_payload), args.adaptation)
    input_kind = derive_input_kind(args.adaptation)
    argv = [
        sys.executable, "-I", service,
        "--listen", "0.0.0.0:39010",
        "--tx-uri", args.tx_uri,
        "--frozen-dir", str(Path(args.tx_payload)),
        "--input-kind", input_kind,
        "--center", str(RF_CENTER_HZ),
        "--sample-rate", str(RF_SAMPLE_RATE),
        "--tx-bw", str(RF_TX_BW_HZ),
        "--tx-atten", str(RF_TX_ATTEN_DB),
        "--rf-path", "direct-cable",
        "--rf-tx-target-rms", repr(RF_TARGET_RMS),
    ]
    print("RADIOML_DUALSDR_LAUNCH adaptation=%s input_kind=%s frozen_dir=%s manifest=%s" %
          (args.adaptation, input_kind, args.tx_payload, manifest))
    print("RADIOML_DUALSDR_LAUNCH_NOTE: 板端 producer 落地前此服务仅监听不发射; "
          "板端是 CLIENT 发起 HELLO")
    os.execv(sys.executable, argv)


def run_self_test():
    """主机侧自检 (无 SDR/无 RF): direct + dc 两种 adaptation 的解析/映射 + 服务文件存在性。

    direct 用 dualsdr 分支的权威 results/tx_payload (18 列, 480 帧); dc 用临时导出的
    22 列 payload (避免硬编码路径)。"""
    checks = []

    def check(name, ok, detail=""):
        checks.append(ok)
        print("SELF-TEST %-40s %s%s" % (name, "PASS" if ok else "FAIL",
                                         (" -- " + detail) if detail else ""))

    # ---- 服务/协议文件存在性 (只读参照) ----
    service = find_pc_tx_service(None)
    check("pc_tx_sdr_fix10.py exists (read-only ref)", os.path.exists(service), service)
    proto = os.path.join(os.path.dirname(service), "fix10_tx_protocol.py")
    check("fix10_tx_protocol.py exists (read-only ref)", os.path.exists(proto), proto)
    bbc = os.path.join(os.path.dirname(service), "build_burst_cli.sh")
    check("build_burst_cli.sh exists (read-only ref)", os.path.exists(bbc), bbc)

    # ---- input_kind 派生一致性 ----
    check("derive input_kind direct == frozen", derive_input_kind("direct") == DIRECT_INPUT_KIND)
    check("derive input_kind dc == +suffix", derive_input_kind("dc-transport") == DC_INPUT_KIND)
    check("adaptation tags distinct", DC.ADAPTATION_DIRECT != DC.ADAPTATION_DC_TRANSPORT)

    # ---- direct 映射 (dualsdr 分支权威 payload) ----
    direct_tx = Path(__file__).resolve().parent.parent.parent / \
        "fix10class24_original_radioml_dualsdr_ab1_work" / "results" / "tx_payload"
    check("direct tx_payload/tx_manifest.tsv exists", (direct_tx / "tx_manifest.tsv").exists(),
          str(direct_tx))
    if (direct_tx / "tx_manifest.tsv").exists():
        rows = parse_tx_manifest(direct_tx / "tx_manifest.tsv", "direct")
        check("direct: 480 rows parsed", len(rows) == 480, "rows=%d" % len(rows))
        m0 = map_row_to_route_d2(rows[0])
        check("direct: 24 columns", len(m0) == 24, "cols=%d" % len(m0))
        check("direct: source_index == selection_id", int(m0[1]) == rows[0]["selection_id"])
        check("direct: file_name == tx_payload_file", m0[22] == rows[0]["tx_payload_file"])
        check("direct: quantized_sha256 == tx_payload_sha256",
              m0[20] == rows[0]["tx_payload_sha256"])
        check("direct: complex_count == 53760", int(m0[12]) == RF_PAYLOAD_COMPLEX)
        check("direct: original_dc_i/original_dc_q == 0",
              m0[8] == "0.0" and m0[9] == "0.0")
        check("direct: ac_rms == native_rms", float(m0[10]) == rows[0]["native_rms"])
        check("direct: rec_scale == unscale", float(m0[11]) == rows[0]["unscale"])
        ok_sizes = all(
            (direct_tx / r["tx_payload_file"]).stat().st_size == 2 * RF_PAYLOAD_COMPLEX * 2
            for r in rows)
        check("direct: all .i16 byte sizes correct", ok_sizes)
        with tempfile.TemporaryDirectory() as td:
            m = build_frozen_dir(direct_tx, "direct", Path(td))
            check("direct: frozen manifest round-trip",
                  (Path(td) / "route_d2_rf_manifest.tsv").exists(), str(m))

    # ---- dc 映射 (临时导出 22 列 payload, 不硬编码路径) ----
    dc_tx = Path(tempfile.mkdtemp(prefix="pc_tx_dc_self_test_")) / "dc_tx"
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, "-I",
             os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "export_radioml_dc_tx_payload.py"),
             "--input-package",
             r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work"
             r"\sdr_rml24_fix10class24_original_radioml_npu_ab1\input_package",
             "--out-dir", str(dc_tx)],
            capture_output=True, text=True)
        if r.returncode != 0 or "RADIOML_DC_TX_PAYLOAD_DONE" not in r.stdout:
            check("dc: export_radioml_dc_tx_payload.py runs",
                  False, "rc=%d\n%s" % (r.returncode, r.stderr[-800:]))
        else:
            check("dc: export_radioml_dc_tx_payload.py runs", True)
            rows = parse_tx_manifest(dc_tx / "tx_manifest.tsv", "dc-transport")
            check("dc: 480 rows parsed", len(rows) == 480, "rows=%d" % len(rows))
            m0 = map_row_to_route_d2(rows[0])
            check("dc: 24 columns", len(m0) == 24, "cols=%d" % len(m0))
            r0 = rows[0]
            check("dc: original_dc_i == dc_i", float(m0[8]) == r0["dc_i"])
            check("dc: original_dc_q == dc_q", float(m0[9]) == r0["dc_q"])
            check("dc: ac_rms == ac_rms", float(m0[10]) == r0["ac_rms"])
            check("dc: rec_scale == inverse_scale", float(m0[11]) == r0["inverse_scale"])
            check("dc: complex_count == 53760", int(m0[12]) == RF_PAYLOAD_COMPLEX)
            ok_sizes = all(
                (dc_tx / r["tx_payload_file"]).stat().st_size == 2 * RF_PAYLOAD_COMPLEX * 2
                for r in rows)
            check("dc: all .i16 byte sizes correct", ok_sizes)
            with tempfile.TemporaryDirectory() as td:
                m = build_frozen_dir(dc_tx, "dc-transport", Path(td))
                check("dc: frozen manifest round-trip",
                      (Path(td) / "route_d2_rf_manifest.tsv").exists(), str(m))
    finally:
        import shutil
        shutil.rmtree(dc_tx.parent, ignore_errors=True)

    all_ok = all(checks)
    print("RADIOML_DUALSDR_PC_TX_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


def main():
    ap = argparse.ArgumentParser(prog="pc_tx_radioml_dualsdr.py")
    sub = ap.add_subparsers(dest="cmd")

    def add_adaptation(parser):
        parser.add_argument("--adaptation", default="direct",
                            choices=["direct", "dc-transport"],
                            help="direct (18-col, byte-identical) | dc-transport (22-col AC)")

    sb = sub.add_parser("build-frozen-dir", help="生成 24 列 route_d2_rf_manifest.tsv")
    sb.add_argument("--tx-payload", required=True,
                    help="tx payload 目录 (含 tx_manifest.tsv + <sid>.i16)")
    sb.add_argument("--out-frozen", default=None,
                    help="可选: 输出目录; 默认原地写回 --tx-payload")
    add_adaptation(sb)

    lb = sub.add_parser("launch", help="exec 现有 PC TX 服务 (板端 producer 落地后使用)")
    lb.add_argument("--tx-payload", required=True)
    lb.add_argument("--tx-uri", default="", help="PC TX SDR 的 libiio URI (必需)")
    lb.add_argument("--pc-tx-service", default=None,
                    help="pc_tx_sdr_fix10.py 路径 (默认 npu-ab1 host_tools)")
    add_adaptation(lb)

    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return run_self_test()
    if args.cmd == "build-frozen-dir":
        return cmd_build_frozen_dir(args)
    if args.cmd == "launch":
        return cmd_launch(args)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
