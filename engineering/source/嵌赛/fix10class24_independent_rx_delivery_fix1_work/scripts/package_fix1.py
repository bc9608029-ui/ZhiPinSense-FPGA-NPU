#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
package_fix1.py -- fix1 第 6 节打包器：确定性扁平 tar（固定 mtime + 名字排序），
产出 PATCH（代码/契约/文档/回归）+ INPUTS（TX 包），并写 SHA 台账。

  产物（--out-dist 目录，必须为空或不存在）：
    fix1_independent_rx_PATCH.tar.gz     脚本+板端头+接线 patch+契约+文档+回归
    fix1_independent_rx_INPUTS.tar.gz    24 个 burst + manifest + SHA256SUMS
    dist_manifest.json                   每个 tar 的 SHA256 + 内容清单

确定性：tar 内条目按 arcname 排序，mtime 固定 0，gzip 用 mtime=0。
Usage:
    python -I scripts/package_fix1.py --out-dist <dist dir>
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATCH_PATHS = [
    "scripts/radioml_independent_rx_contract.py",
    "scripts/radioml_waveform_correctness.py",
    "scripts/radioml_public_protocol_tx.py",
    "scripts/radioml_independent_rx_replay.py",
    "scripts/judge_radioml_independent_rx.py",
    "scripts/package_fix1.py",
    "scripts/radioml_clean_contract.py",       # frozen vendored（逐字，未改）
    "scripts/radioml_dualsdr_common.py",       # frozen vendored（逐字，未改）
    "scripts/radioml_dualsdr_burst.py",        # frozen vendored（逐字，未改）
    "board_package/radioml_independent_rx_runner.hpp",
    "board_package/gate9_wiring.patch",
    "contract/public_protocol_amplitude_contract.json",
    "contract/public_protocol_amplitude_contract.md",
    "contract/waveform_correctness.json",
    "host_tests/run_regression.py",
    "docs/BOARDTEST.md",
    "docs/AUDIT_NOTES.md",
]

INPUTS_PATHS = ["tx_package"]  # 整个 TX 目录


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def tar_bytes(root: Path, rels) -> bytes:
    """确定性扁平 tar.gz：arcname 排序，mtime=0，gzip mtime=0。"""
    buf = io.BytesIO()
    # mode="w"（内存未压缩 tar）→ 下面单层 gzip mtime=0 包装，避免旧 mode="w:gz"
    # + 再 gzip 的双重压缩缺陷（导致标准 tar 无法解包）。
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for rel in sorted(rels):
            p = root / rel
            if p.is_dir():
                for f in sorted(p.rglob("*")):
                    if f.is_file():
                        arc = str(f.relative_to(root)).replace("\\", "/")
                        ti = tarfile.TarInfo(arc)
                        ti.size = f.stat().st_size
                        ti.mtime = 0
                        ti.mode = 0o644
                        with open(f, "rb") as fh:
                            tf.addfile(ti, fh)
            else:
                arc = rel.replace("\\", "/")
                ti = tarfile.TarInfo(arc)
                ti.size = p.stat().st_size
                ti.mtime = 0
                ti.mode = 0o644
                with open(p, "rb") as fh:
                    tf.addfile(ti, fh)
    # gzip header mtime 归零：单层 gzip 包装（tar 本体未压缩，见上）
    raw = buf.getvalue()
    import gzip
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=0) as gz:
        gz.write(raw)
    return out.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dist", default=str(ROOT / "dist"))
    args = ap.parse_args()
    dist = Path(args.out_dist)
    if dist.exists() and any(dist.iterdir()):
        raise SystemExit("ERROR: --out-dist not empty (refuse overwrite): %s" % dist)
    dist.mkdir(parents=True, exist_ok=True)

    missing = [r for r in PATCH_PATHS if not (ROOT / r).exists()]
    if missing:
        raise SystemExit("ERROR: missing PATCH files: %s" % missing)

    patch_bytes = tar_bytes(ROOT, PATCH_PATHS)
    patch_name = "fix1_independent_rx_PATCH.tar.gz"
    (dist / patch_name).write_bytes(patch_bytes)

    inputs_bytes = tar_bytes(ROOT, INPUTS_PATHS)
    inputs_name = "fix1_independent_rx_INPUTS.tar.gz"
    (dist / inputs_name).write_bytes(inputs_bytes)

    manifest = {
        "token": "M29-RML24-FIX10CLASS24-INDEPENDENT-RX-DELIVERY-FIX1-DIST",
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tarballs": {
            patch_name: {"sha256": sha256_bytes(patch_bytes),
                         "bytes": len(patch_bytes),
                         "files": sorted(PATCH_PATHS)},
            inputs_name: {"sha256": sha256_bytes(inputs_bytes),
                          "bytes": len(inputs_bytes),
                          "note": "24 public-protocol bursts + manifest + SHA256SUMS"},
        },
        "honest_gap": "board C++ (radioml_independent_rx_runner.hpp + gate9_wiring.patch) "
                      "未在 aarch64 上编译（Windows 主机无交叉工具链）；上板前 make -j1 "
                      "原生构建并以 host 数字参考核验 1/S 归一化。",
    }
    with open(dist / "dist_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    print("PACKAGE PATCH  %s  sha256=%s  bytes=%d" %
          (patch_name, manifest["tarballs"][patch_name]["sha256"], len(patch_bytes)))
    print("PACKAGE INPUTS %s  sha256=%s  bytes=%d" %
          (inputs_name, manifest["tarballs"][inputs_name]["sha256"], len(inputs_bytes)))
    print("PACKAGE_DONE out_dist=%s" % dist)
    return 0


if __name__ == "__main__":
    sys.exit(main())
