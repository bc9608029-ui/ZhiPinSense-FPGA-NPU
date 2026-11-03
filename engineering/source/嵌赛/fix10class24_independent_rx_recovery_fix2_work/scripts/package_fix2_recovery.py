#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""package_fix2_recovery.py -- 打包 fix1v2-independent-rx-recovery-fix2 PATCH。

基线 = fix1v2 board impl1 树（fix1v2_board_impl1 已应用）。本 PATCH 在其上应用 fix2：
A 线恢复链（联合 cfo+τ 估计 + τ=0 恒等修正）、B 线 FFT 同步/资源计量、C 线回归测试、
23 列判读器、报告。关键：tar 用 mode="w"（plain tar）再 gzip 一次 → 恰好单层 gzip
（修 F0 双 gzip 坑）；mtime=0 确定性；逐文件 SHA256SUMS。
"""
import gzip
import hashlib
import io
import json
import os
import tarfile

WORK = r"F:\嵌赛\fix10class24_independent_rx_recovery_fix2_work"
DIST = os.path.join(WORK, "dist")
TARBALL = "fix2_recovery_PATCH.tar.gz"

# archive_path (相对基线树根) -> source_path (fix2 树内)
FILES = {
    # A 线 + B 线：板端 C++（改/新）
    "board_package/radioml_independent_rx_public_recovery.hpp": os.path.join(WORK, "board_package", "radioml_independent_rx_public_recovery.hpp"),
    "board_package/radioml_independent_rx_runner.hpp": os.path.join(WORK, "board_package", "radioml_independent_rx_runner.hpp"),
    "board_package/radioml_independent_rx_fft.hpp": os.path.join(WORK, "board_package", "radioml_independent_rx_fft.hpp"),
    "sdr_adapter/latency_stats.hpp": os.path.join(WORK, "sdr_adapter", "latency_stats.hpp"),
    # 判读器（21→23 列）
    "scripts/judge_radioml_independent_rx_board.py": os.path.join(WORK, "scripts", "judge_radioml_independent_rx_board.py"),
    # A 线 Python 契约 + 诊断（新）
    "scripts/radioml_independent_rx_recovery_fix2.py": os.path.join(WORK, "scripts", "radioml_independent_rx_recovery_fix2.py"),
    "scripts/reproduce_fix2_diagnosis.py": os.path.join(WORK, "scripts", "reproduce_fix2_diagnosis.py"),
    "scripts/a_line_interp_test.py": os.path.join(WORK, "scripts", "a_line_interp_test.py"),
    "scripts/a_line_split_validation.py": os.path.join(WORK, "scripts", "a_line_split_validation.py"),
    "scripts/diagnose_fix2_part2.py": os.path.join(WORK, "scripts", "diagnose_fix2_part2.py"),
    "scripts/export_fix2_cpp_reference.py": os.path.join(WORK, "scripts", "export_fix2_cpp_reference.py"),
    "scripts/fix2_diagnosis.json": os.path.join(WORK, "scripts", "fix2_diagnosis.json"),
    "scripts/_build_bline.sh": os.path.join(WORK, "scripts", "_build_bline.sh"),
    "scripts/package_fix2_recovery.py": os.path.join(WORK, "scripts", "package_fix2_recovery.py"),
    # C 线 host 测试（新）
    "host_tests/test_recovery_fix2.cpp": os.path.join(WORK, "host_tests", "test_recovery_fix2.cpp"),
    "host_tests/test_sync_bench.cpp": os.path.join(WORK, "host_tests", "test_sync_bench.cpp"),
    "host_tests/test_sync_fft_invariant.cpp": os.path.join(WORK, "host_tests", "test_sync_fft_invariant.cpp"),
    "host_tests/syntax_runner_template.cpp": os.path.join(WORK, "host_tests", "syntax_runner_template.cpp"),
    # 文档（新）
    "docs/RECOVERY_FIX2_BLINE_EFFICIENCY.md": os.path.join(WORK, "docs", "RECOVERY_FIX2_BLINE_EFFICIENCY.md"),
    "docs/RECOVERY_FIX2_REPORT.md": os.path.join(WORK, "docs", "RECOVERY_FIX2_REPORT.md"),
    "docs/BOARDTEST_FIX2.md": os.path.join(WORK, "docs", "BOARDTEST_FIX2.md"),
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    # 1. per-file SHA256SUMS (LF, no CRLF translation)
    sums_lines = []
    member_bytes = {}
    for arc, src in FILES.items():
        b = open(src, "rb").read()
        member_bytes[arc] = b
        sums_lines.append("%s  %s" % (sha256_bytes(b), arc))
    sums_content = ("\n".join(sums_lines) + "\n").encode("utf-8")
    member_bytes["SHA256SUMS.txt"] = sums_content

    # 2. plain tar in memory (mode="w"), then gzip ONCE
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for arc in sorted(member_bytes):
            b = member_bytes[arc]
            ti = tarfile.TarInfo(name=arc)
            ti.size = len(b)
            ti.mtime = 0  # deterministic
            tf.addfile(ti, io.BytesIO(b))
    gz = gzip.compress(buf.getvalue(), mtime=0)

    out = os.path.join(DIST, TARBALL)
    os.makedirs(DIST, exist_ok=True)
    open(out, "wb").write(gz)

    # 3. self-check: single gzip layer + members
    d1 = gzip.decompress(gz)
    assert d1[:3] != b"\x1f\x8b\x08", "DOUBLE GZIP detected"
    tf = tarfile.open(fileobj=io.BytesIO(d1), mode="r:")
    names = tf.getnames()
    tf.close()
    assert set(names) == set(member_bytes), "member mismatch: %s" % (set(names) ^ set(member_bytes))

    tarball_sha = sha256_bytes(gz)
    print("TARBALL=%s" % out)
    print("TARBALL_SHA256=%s" % tarball_sha)
    print("BYTES=%d  MEMBERS=%d  SINGLE_GZIP=OK" % (len(gz), len(names)))

    manifest = {
        "built_note": "fix1v2-independent-rx-recovery-fix2 PATCH（A/B/C 三线 + 主线程收口），单层 gzip；"
                      "基线 = fix1v2 board impl1 树；输入复用 v1/v2 tx_package（已冻结交付）",
        "baseline": "fix10class24_fix1v2_board_impl1_work",
        "tarball": TARBALL,
        "sha256": tarball_sha,
        "bytes": len(gz),
        "members": sorted(names),
    }
    mpath = os.path.join(DIST, "fix2_dist_manifest.json")
    open(mpath, "wb").write(json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))
    print("MANIFEST=%s" % mpath)
    for arc in sorted(names):
        print("  %-52s %s" % (arc, sha256_bytes(member_bytes[arc])[:16]))


if __name__ == "__main__":
    main()
