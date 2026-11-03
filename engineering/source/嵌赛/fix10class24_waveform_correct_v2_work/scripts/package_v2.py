#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
package_v2.py -- 波形正确性 v2 打包器（确定性扁平 tar + SHA 台账），结构与 fix1 打包器同。

产物（--out-dist）：
    v2_waveform_correct_PATCH.tar.gz   脚本+契约+文档+回归（v2 模块 + 冻结 vendored）
    v2_waveform_correct_INPUTS.tar.gz  24 个 v2 burst + manifest + SHA256SUMS
    dist_manifest.json                 每个 tar 的 SHA256 + 内容清单 + 诚实缺口
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATCH_PATHS = [
    "scripts/radioml_waveform_correct_v2.py",
    "scripts/radioml_v2_contract.py",
    "scripts/radioml_v2_tx.py",
    "scripts/radioml_v2_replay.py",
    "scripts/judge_radioml_v2.py",
    "scripts/package_v2.py",
    "scripts/radioml_clean_contract.py",       # frozen vendored（逐字，未改）
    "scripts/radioml_dualsdr_common.py",       # frozen vendored（逐字，未改）
    "scripts/radioml_dualsdr_burst.py",        # frozen vendored（逐字，未改）
    "scripts/radioml_independent_rx_contract.py",  # fix1 vendored（逐字，未改）
    "contract/v2_waveform_definitions.md",
    "contract/v2_waveform_correctness.json",
    "host_tests/run_regression_v2.py",
    "docs/v2_AUDIT_NOTES.md",
]
INPUTS_PATHS = ["tx_package"]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def tar_bytes(root: Path, rels) -> bytes:
    buf = io.BytesIO()
    # mode="w" (uncompressed tar in memory) so the single gzip wrap below sets
    # mtime=0 without DOUBLE-compressing (the old mode="w:gz" + re-gzip bug).
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
    raw = buf.getvalue()
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
    patch_name = "v2_waveform_correct_PATCH.tar.gz"
    (dist / patch_name).write_bytes(patch_bytes)

    inputs_bytes = tar_bytes(ROOT, INPUTS_PATHS)
    inputs_name = "v2_waveform_correct_INPUTS.tar.gz"
    (dist / inputs_name).write_bytes(inputs_bytes)

    manifest = {
        "token": "M29-RML24-FIX10CLASS24-WAVEFORM-CORRECT-V2-DIST",
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tarballs": {
            patch_name: {"sha256": sha256_bytes(patch_bytes),
                         "bytes": len(patch_bytes), "files": sorted(PATCH_PATHS)},
            inputs_name: {"sha256": sha256_bytes(inputs_bytes),
                          "bytes": len(inputs_bytes),
                          "note": "24 v2 bursts + manifest + SHA256SUMS"},
        },
        "v1_untouched_proof": {
            "v1_patch_sha": "06c3ce495e2415d9f8b343f11c9e1c0923e897aa7a8d6b5465c56f7dce94df79",
            "v1_inputs_sha": "898bcaa50530e8a06345d4163f3845f7c79ca0fbf8ff6ce45090a4e9a99a7466",
            "note": "v1 在 fix10class24_independent_rx_delivery_fix1_work/ 逐字不动；"
                    "本 v2 在独立目录 fix10class24_waveform_correct_v2_work/。",
        },
        "honest_gap": "纯离线；不碰板/不发射/不训练；板端 C++ 未在 aarch64 编译。",
    }
    with open(dist / "dist_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    print("PACKAGE_V2 PATCH  %s  sha256=%s  bytes=%d" %
          (patch_name, manifest["tarballs"][patch_name]["sha256"], len(patch_bytes)))
    print("PACKAGE_V2 INPUTS %s  sha256=%s  bytes=%d" %
          (inputs_name, manifest["tarballs"][inputs_name]["sha256"], len(inputs_bytes)))
    print("PACKAGE_V2_DONE out_dist=%s" % dist)
    return 0


if __name__ == "__main__":
    sys.exit(main())
