#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_e2e_sim.py — M29-RML24-REALRF-FINETUNE-PILOT1 / 线 B：24 帧端到端模拟把关。

这是评审结论「修完并在干净目录做一次 24 帧端到端模拟」的落地脚本。它：

  1. 用 WSL g++ 编译板端树里的 C++ `pilot1_e2e_sim`（真实 loader + 真实 32 字段
     emit + 真实 sdr::Sha256，iCraft/libiio/SDR-free）；
  2. 在**干净临时目录**里跑它对**真实 S1 tx_manifest.tsv**（240 行）取每类 1 帧
     （24 帧）落盘；
  3. 交叉校验产物：
     * 判读器 `judge_realrf_pilot.read_tsv` 能按 32 字段 CAPTURE_COLS 解析（表头逐
       字节一致、24 行、每行恰 32 字段）—— 证明判读器能消费真实板端保存路径；
     * save-before-gate 不变式（门拒帧仍带 model_input/logits/双预测；hard-invalid
       帧带 raw_rx 但张量 SHA 为空）；
     * C++ 的 manifest_sha256 == Python `Pilot1IdentityManifest.sha256()`（跨语言逐字节一致）。

纯离线：不上板、不发射、不训练。退出码 0 = 全 PASS。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LINE_B = HERE.parent
OFFLINE_ROOT = LINE_B.parent

DEFAULT_BOARD_ROOT = Path(
    r"F:\嵌赛\fix10class24_dualsdr_rf_adapt_prep1_work"
    r"\sdr_rml24_fix10class24_dualsdr_rf_adapt_prep1"
)
DEFAULT_S1_MANIFEST_DIR = OFFLINE_ROOT / "line_b" / "tx_payload" / "S1"
DEFAULT_JUDGE = OFFLINE_ROOT / "line_c" / "scripts" / "judge_realrf_pilot.py"

N_FRAMES = 24
N_FIELDS = 32


def _win_to_wsl(p: Path) -> str:
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return "/mnt/" + s[0].lower() + s[2:]
    return s


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load %s from %s" % (name, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _is_hex64(v: str) -> bool:
    return len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def _is_int(v: str) -> bool:
    try:
        int(v)
        return True
    except (TypeError, ValueError):
        return False


def build_sim(board_root: Path) -> Path:
    ht = board_root / "host_tests"
    src = ht / "pilot1_e2e_sim.cpp"
    if not src.is_file():
        raise SystemExit("C++ sim source not found: %s" % src)
    cmd = (
        "cd %s && g++ -std=gnu++17 -O2 -Wall -Wextra -Werror "
        "-I../board_package -I../sdr_adapter -I../ui_sw "
        "pilot1_e2e_sim.cpp -o bin/pilot1_e2e_sim"
    ) % _win_to_wsl(ht)
    p = subprocess.run(["wsl.exe", "-e", "bash", "-lc", cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if p.returncode != 0:
        raise SystemExit("C++ sim build failed:\n%s\n%s" % (p.stdout, p.stderr))
    return ht / "bin" / "pilot1_e2e_sim"


def run_sim(bin_path: Path, s1_manifest_dir: Path, out_dir: Path) -> Path:
    manifest_tsv = s1_manifest_dir / "tx_manifest.tsv"
    if not manifest_tsv.is_file():
        raise SystemExit("S1 manifest not found: %s" % manifest_tsv)
    cmd = "%s --tx-manifest=%s --out-dir=%s" % (
        _win_to_wsl(bin_path), _win_to_wsl(manifest_tsv), _win_to_wsl(out_dir))
    p = subprocess.run(["wsl.exe", "-e", "bash", "-lc", cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if p.returncode != 0:
        raise SystemExit("C++ sim run failed:\n%s\n%s" % (p.stdout, p.stderr))
    return out_dir / "capture_sim_S1.tsv"


def verify(tsv_path: Path, summary_path: Path, judge_path: Path,
           manifest_module, s1_manifest_dir: Path) -> list[str]:
    problems: list[str] = []

    # (1) 判读器能解析（表头 32 字段 + 24 行 + 每行 32 字段）。
    judge = _load_module("judge_realrf_pilot", judge_path)
    try:
        rows = judge.read_tsv(tsv_path, judge.CAPTURE_COLS)
    except SystemExit as e:
        problems.append("judge.read_tsv failed: %s" % e)
        rows = []
    if len(rows) != N_FRAMES:
        problems.append("judge.read_tsv parsed %d rows (want %d)" % (len(rows), N_FRAMES))

    # (2) save-before-gate 不变式。
    n_gate_reject = n_hard = 0
    for r in rows:
        sid = r["source_id"]
        if not _is_hex64(r["raw_rx_sha256"]):
            problems.append("%s raw_rx_sha256 not 64-hex" % sid)
        if r["hard_invalid"] == "1":
            n_hard += 1
            if r["model_input_sha256"] or r["logits_sha256"] or r["board_pred1"] or r["board_pred2"]:
                problems.append("%s hard-invalid leaked tensor/pred" % sid)
        else:
            if not (_is_hex64(r["model_input_sha256"]) and _is_hex64(r["logits_sha256"])):
                problems.append("%s missing tensor SHA" % sid)
            if not (_is_int(r["board_pred1"]) and _is_int(r["board_pred2"])):
                problems.append("%s missing board pred" % sid)
            if r["gate_pass"] == "0":
                n_gate_reject += 1
                if not r["failure_token"]:
                    problems.append("%s gate-reject without failure_token" % sid)
    # 合成口径：20 valid / 3 gate-reject / 1 hard-invalid。
    if n_hard != 1:
        problems.append("hard_invalid count %d != 1" % n_hard)
    if n_gate_reject != 3:
        problems.append("gate_reject count %d != 3" % n_gate_reject)

    # (3) 跨语言 manifest SHA 逐字节一致。
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    cpp_sha = summary.get("manifest_sha256", "")
    py_sha = manifest_module.Pilot1IdentityManifest(str(s1_manifest_dir)).sha256()
    if not _is_hex64(cpp_sha):
        problems.append("summary manifest_sha256 not 64-hex: %r" % cpp_sha)
    if py_sha != cpp_sha:
        problems.append("manifest SHA mismatch: C++=%s Python=%s" % (cpp_sha, py_sha))
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board-root", type=Path, default=DEFAULT_BOARD_ROOT)
    ap.add_argument("--s1-manifest-dir", type=Path, default=DEFAULT_S1_MANIFEST_DIR)
    ap.add_argument("--judge", type=Path, default=DEFAULT_JUDGE)
    ap.add_argument("--keep-out", action="store_true", help="keep the clean temp dir")
    args = ap.parse_args()

    manifest_module = _load_module(
        "pilot1_tx_manifest",
        args.board_root / "host_tools" / "pilot1_tx_manifest.py")

    print("== [1/3] build C++ pilot1_e2e_sim (WSL g++) ==")
    bin_path = build_sim(args.board_root)

    tmp = Path(tempfile.mkdtemp(prefix="pilot1_e2e_sim_"))
    if args.keep_out:
        print("clean out-dir: %s" % tmp)
    print("== [2/3] run 24-frame sim against real S1 manifest ==")
    tsv_path = run_sim(bin_path, args.s1_manifest_dir, tmp)
    summary_path = tmp / "capture_sim_summary.json"

    print("== [3/3] cross-check (judge parse + save-before-gate + manifest SHA) ==")
    problems = verify(tsv_path, summary_path, args.judge, manifest_module,
                      args.s1_manifest_dir)
    if problems:
        for p in problems:
            print("FAIL: %s" % p)
        print("PILOT1_E2E_SIM_HARNESS FAIL (%d problems)" % len(problems))
        return 1
    print("PILOT1_E2E_SIM_HARNESS PASS: 24/24 rows parsed by judge; "
          "save-before-gate invariants hold; manifest SHA byte-identical C++/Python")
    if not args.keep_out:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
