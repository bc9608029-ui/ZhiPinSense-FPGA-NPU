#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""package_fix1v2_board_impl1.py -- 打包 fix1v2 board impl1 (G1-G4) PATCH。

关键：tar 用 mode="w"（plain tar），再 gzip 一次 → 恰好单层 gzip（修 F0 双 gzip 坑）。
打包后自校验：gzip.decompress 一次必须是合法 tar（不是第二个 gzip 层）。
"""
import gzip
import hashlib
import io
import json
import os
import tarfile

WORK = r"F:\嵌赛\fix10class24_fix1v2_board_impl1_work"
DIST = os.path.join(WORK, "dist")
TARBALL = "fix1v2_board_impl1_PATCH.tar.gz"

# archive_path -> source_path
FILES = {
    "board_package/gate9_wiring.patch": os.path.join(WORK, "board_package", "gate9_wiring.patch"),
    "board_package/radioml_independent_rx_loader.hpp": os.path.join(WORK, "board_package", "radioml_independent_rx_loader.hpp"),
    "board_package/radioml_independent_rx_public_recovery.hpp": os.path.join(WORK, "board_package", "radioml_independent_rx_public_recovery.hpp"),
    "board_package/radioml_independent_rx_runner.hpp": os.path.join(WORK, "board_package", "radioml_independent_rx_runner.hpp"),
    "host_tools/fix10_tx_protocol.py": os.path.join(WORK, "host_tools", "fix10_tx_protocol.py"),
    "host_tools/pc_tx_sdr_fix10_public.py": os.path.join(WORK, "host_tools", "pc_tx_sdr_fix10_public.py"),
    "host_tests/test_radioml_independent_rx.cpp": os.path.join(WORK, "host_tests", "test_radioml_independent_rx.cpp"),
    "host_tests/test_pc_tx_simulated_device.py": os.path.join(WORK, "host_tests", "test_pc_tx_simulated_device.py"),
    "scripts/audit_old_tarballs.py": os.path.join(WORK, "scripts", "audit_old_tarballs.py"),
    "scripts/judge_radioml_independent_rx_board.py": os.path.join(WORK, "scripts", "judge_radioml_independent_rx_board.py"),
    "scripts/digital_baseline_identity.json": os.path.join(WORK, "scripts", "digital_baseline_identity.json"),
    "scripts/package_fix1v2_board_impl1.py": os.path.join(WORK, "scripts", "package_fix1v2_board_impl1.py"),
    "dist/old_tarball_audit.json": os.path.join(WORK, "dist", "old_tarball_audit.json"),
    "docs/G1G4_COMPLETION_REPORT.md": os.path.join(WORK, "docs", "G1G4_COMPLETION_REPORT.md"),
    "docs/BOARDTEST.md": os.path.join(WORK, "docs", "BOARDTEST.md"),
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
        "built_note": "fix1v2 board impl1 (G1-G4 板端实装收口) PATCH，单层 gzip；输入复用 fix1/v2 INPUTS",
        "baseline": "fix10class24_original_radioml_dc_ab1_work/board_package/",
        "tarball": TARBALL,
        "sha256": tarball_sha,
        "bytes": len(gz),
        "members": sorted(names),
    }
    mpath = os.path.join(DIST, "dist_manifest.json")
    open(mpath, "wb").write(json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))
    print("MANIFEST=%s" % mpath)
    for arc in sorted(names):
        print("  %-52s %s" % (arc, sha256_bytes(member_bytes[arc])[:16]))


if __name__ == "__main__":
    main()
