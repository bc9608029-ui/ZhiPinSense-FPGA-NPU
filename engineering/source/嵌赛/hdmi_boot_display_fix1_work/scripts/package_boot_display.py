#!/usr/bin/env python3
"""package_boot_display.py -- hdmi-boot-display-fix1 交付物打包。

产物：
  dist/hdmi_boot_display_fix1.tar.gz   单层 gzip（tar->gzip，无双重压缩，避 F0 坑）
  dist/SHA256SUMS.txt                  仅一行：tar.gz 的 SHA256（传输校验）
  tar 内 SHA256SUMS.txt                11 个成员的 SHA256（解包后成员校验，不含自身）

- 确定性 tar：固定 mtime/uid/gid/uname/gname、按路径排序、文本按 bytes 原样写入
  （不经过 text 模式换行翻译，避 Windows CRLF/SHA 漂移坑）。
- 全部 SHA 在打包后对实际产出的字节计算，保证逐字节一致。
"""
import hashlib
import io
import os
import sys
import tarfile
import gzip

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
TAR_GZ_NAME = "hdmi_boot_display_fix1.tar.gz"

# 交付物（相对工作树根）。全部为文本，逐字节原样入包。
FILES = [
    "docs/ROOT_CAUSE_AUDIT.md",
    "docs/BOOT_DISPLAY_FIX_PLAN.md",
    "docs/BOARDTEST.md",
    "docs/ROLLBACK.md",
    "scripts/boot_display.sh",
    "scripts/boot_display.service",
    "scripts/install_boot_display.sh",
    "scripts/uninstall_boot_display.sh",
    "scripts/collect_boot_display_state.sh",
    "scripts/package_boot_display.py",
    "host_tests/check_boot_display.sh",
]

FIXED_MTIME = 1700000000
FIXED_MODE = 0o644


def _read(rel: str) -> bytes:
    with open(os.path.join(ROOT, rel.replace("/", os.sep)), "rb") as f:
        return f.read()


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_member_sums() -> bytes:
    lines = []
    for rel in sorted(FILES):
        lines.append("%s  %s\n" % (sha256_of_bytes(_read(rel)), rel))
    return "".join(lines).encode("utf-8")


def build_tar_bytes(member_sums: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        def add(name: str, data: bytes):
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mtime = FIXED_MTIME
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mode = FIXED_MODE
            tar.addfile(info, io.BytesIO(data))

        for rel in sorted(FILES):
            add(rel, _read(rel))
        add("SHA256SUMS.txt", member_sums)
    return buf.getvalue()


def gzip_bytes(data: bytes) -> bytes:
    out = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=out, mtime=FIXED_MTIME) as gz:
        gz.write(data)
    return out.getvalue()


def main() -> int:
    os.makedirs(DIST, exist_ok=True)
    missing = [f for f in FILES if not os.path.isfile(os.path.join(ROOT, f.replace("/", os.sep)))]
    if missing:
        print("FAIL missing files: %s" % ", ".join(missing))
        return 1

    member_sums = build_member_sums()
    tar_bytes = build_tar_bytes(member_sums)
    gz_bytes = gzip_bytes(tar_bytes)

    with open(os.path.join(DIST, TAR_GZ_NAME), "wb") as f:
        f.write(gz_bytes)

    # dist/SHA256SUMS.txt：仅 tar.gz 一行（从 dist/ 目录可校验传输）
    with open(os.path.join(DIST, "SHA256SUMS.txt"), "wb") as f:
        f.write(("%s  %s\n" % (sha256_of_bytes(gz_bytes), TAR_GZ_NAME)).encode("utf-8"))

    print("PACKAGE_OK dist/%s (%d bytes, %d members + SHA256SUMS.txt)" % (
        TAR_GZ_NAME, len(gz_bytes), len(FILES)))
    print("  tar.gz  %s" % sha256_of_bytes(gz_bytes))
    print("  校验传输: cd dist && sha256sum -c SHA256SUMS.txt")
    print("  校验成员: tar xzf %s && cd <解包目录> && sha256sum -c SHA256SUMS.txt" % TAR_GZ_NAME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
