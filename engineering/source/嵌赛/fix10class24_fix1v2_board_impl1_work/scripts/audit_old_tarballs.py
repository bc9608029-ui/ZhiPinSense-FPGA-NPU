#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_old_tarballs.py -- 遍历 F:\\嵌赛\\*\\dist\\*.tar.gz，做标准单层解包检查。

判定口径：
  * 读文件 -> gzip.decompress 一次：
      - 解出的是合法 tar（tarfile r: 能列成员）        -> 「单层 OK」(single-layer tar.gz)
      - 解出的还是 gzip 流（magic 1f8b08，二次 gzip）   -> 「双重 gzip 损坏」(double-gzip)
      - 解出既非 tar 又非 gzip                          -> 「损坏/未知」
  * 与 tarfile.open(mode="r:gz") 直接打开作交叉验证（标准工具视角）。

只报告，不修改任何包（重打包是另一步，须逐包判定）。
"""
from __future__ import annotations

import gzip
import io
import json
import tarfile
import hashlib
import sys
from pathlib import Path

ROOT = Path(r"F:\嵌赛")
GZIP_MAGIC = b"\x1f\x8b\x08"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def classify(path: Path):
    raw = path.read_bytes()
    h = sha256_bytes(raw)
    sz = len(raw)
    try:
        d1 = gzip.decompress(raw)
    except Exception as e:
        return {"status": "CORRUPT", "detail": "gzip.decompress failed: %s" % e,
                "sha256": h, "bytes": sz}
    # d1 is a tar?
    try:
        tf = tarfile.open(fileobj=io.BytesIO(d1), mode="r:")
        members = len(tf.getmembers())
        tf.close()
        # also cross-check standard r:gz
        try:
            tf2 = tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz")
            n2 = len(tf2.getmembers())
            tf2.close()
            x = "r:gz also OK (%d)" % n2
        except Exception as e2:
            x = "r:gz FAILED: %s" % str(e2).splitlines()[0][:80]
        return {"status": "SINGLE_OK", "members": members, "cross_check": x,
                "sha256": h, "bytes": sz}
    except Exception:
        pass
    # d1 not a tar; is it gzip again?
    if d1[:3] == GZIP_MAGIC:
        return {"status": "DOUBLE_GZIP_BROKEN", "detail": "second gzip layer",
                "sha256": h, "bytes": sz}
    return {"status": "CORRUPT", "detail": "not tar after single gunzip",
            "sha256": h, "bytes": sz}


def main() -> int:
    tars = sorted(ROOT.glob("**/dist/*.tar.gz"))
    rows = {}
    for p in tars:
        rows[str(p.relative_to(ROOT))] = classify(p)

    by_status = {}
    for rel, r in rows.items():
        by_status.setdefault(r["status"], []).append(rel)

    for s in ["SINGLE_OK", "DOUBLE_GZIP_BROKEN", "CORRUPT"]:
        lst = by_status.get(s, [])
        print("== %s: %d ==" % (s, len(lst)))
        for rel in lst:
            r = rows[rel]
            extra = ""
            if s != "SINGLE_OK":
                extra = "  %s" % (r.get("detail") or r.get("cross_check") or "")
            else:
                extra = "  members=%d  %s" % (r["members"], r["cross_check"])
            print("  %-95s %s%s" % (rel, r["sha256"][:16], extra))

    total = len(rows)
    print("\nTOTAL=%d  SINGLE_OK=%d  DOUBLE_GZIP_BROKEN=%d  CORRUPT=%d" %
          (total, len(by_status.get("SINGLE_OK", [])),
           len(by_status.get("DOUBLE_GZIP_BROKEN", [])),
           len(by_status.get("CORRUPT", []))))

    out = Path(r"F:\嵌赛\fix10class24_fix1v2_board_impl1_work\dist\old_tarball_audit.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(json.dumps(
        {"total": total, "rows": {k: v for k, v in rows.items()}},
        indent=2, sort_keys=True).encode("utf-8"))
    print("AUDIT_JSON=%s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
