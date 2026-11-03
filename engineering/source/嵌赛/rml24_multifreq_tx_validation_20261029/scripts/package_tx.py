#!/usr/bin/env python3
"""Package the multi-frequency TX offline deliverables (deterministic archive).

Produces, under ``dist/``:
  - rml24_multifreq_tx_validation_offline_20261029.tar.gz   (deterministic gzip tar)
  - SHA256SUMS.txt                                           (internal, one line per file)
  - ARCHIVE_SHA256.txt                                       (out-of-archive whole-archive SHA)

Then independently unpacks the archive into a fresh temp dir and re-verifies
every file against SHA256SUMS (fail-closed: any mismatch or missing file -> rc 1).
"""
from __future__ import annotations

import gzip
import hashlib
import io
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
ARCHIVE = "rml24_multifreq_tx_validation_offline_20261029.tar.gz"

# Explicit file manifest (relative to ROOT); nothing else is packaged.
FILES = [
    "HANDOFF_MULTIFREQUENCY_TX.md",
    "CONTRACT.json",
    "docs/BOARDTEST_MULTIFREQUENCY_TX.md",
    "scripts/tx_common.py",
    "scripts/verify_tx_offline.py",
    "scripts/multifreq_tx.py",
    "scripts/selftest_tx.py",
    "scripts/package_tx.py",
    "results/verify_offline/verification_report.json",
    "results/verify_offline/verdict.json",
    "results/verify_offline/psd_dual.png",
    "results/verify_offline/wave_a_only.c16",
    "results/verify_offline/wave_b_only.c16",
    "results/verify_offline/wave_both.c16",
    "results/verify_offline/wave_silence.c16",
    "results/tx_dryrun/dry_run_report.json",
    "results/tx_dryrun/device_a_only.i16",
    "results/tx_dryrun/device_b_only.i16",
    "results/tx_dryrun/device_both.i16",
    "results/tx_dryrun/device_silence.i16",
]


def _sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_archive() -> None:
    DIST.mkdir(parents=True, exist_ok=True)

    # fail-closed: every manifest file must exist first
    missing = [f for f in FILES if not (ROOT / f).is_file()]
    if missing:
        raise SystemExit("MISSING_FILES " + repr(missing))

    sums: list[str] = []
    for rel in sorted(FILES):
        p = ROOT / rel
        sums.append(f"{_sha_file(p)}  {rel}")

    # deterministic gzip tar: fixed mtime/uid/gid, sorted order, no __pycache__
    buf = io.BytesIO()
    with gzip.GzipFile(filename=ARCHIVE, mode="wb", fileobj=buf, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for rel in sorted(FILES):
                p = ROOT / rel
                info = tar.gettarinfo(str(p), arcname=rel)
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with open(p, "rb") as f:
                    tar.addfile(info, f)

    archive_bytes = buf.getvalue()
    (DIST / ARCHIVE).write_bytes(archive_bytes)
    (DIST / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    (DIST / "ARCHIVE_SHA256.txt").write_text(_sha_file(DIST / ARCHIVE) + f"  {ARCHIVE}\n", encoding="utf-8")
    print(f"PACKAGED {DIST / ARCHIVE} ({len(archive_bytes)} bytes, {len(FILES)} files)")
    print(f"ARCHIVE_SHA256 {_sha_file(DIST / ARCHIVE)}")


def _independent_verify() -> int:
    archive = DIST / ARCHIVE
    expected_sums = {}
    for line in (DIST / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, rel = line.split("  ", 1)
        expected_sums[rel] = digest

    with tempfile.TemporaryDirectory() as td:
        unpack = Path(td)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(unpack, filter="data")  # our own deterministic archive
        problems = []
        for rel, digest in expected_sums.items():
            p = unpack / rel
            if not p.is_file():
                problems.append(f"{rel}: MISSING")
            elif _sha_file(p) != digest:
                problems.append(f"{rel}: SHA_MISMATCH")
        extra = sorted(p.relative_to(unpack).as_posix() for p in unpack.rglob("*") if p.is_file()
                       and p.relative_to(unpack).as_posix() not in expected_sums)
        if extra:
            problems.append("EXTRA_FILES " + repr(extra))
        if problems:
            print("UNPACK_VERIFY_FAIL " + repr(problems))
            return 1
    print("UNPACK_VERIFY_OK " + f"{len(expected_sums)} files")
    return 0


def main() -> int:
    _build_archive()
    return _independent_verify()


if __name__ == "__main__":
    raise SystemExit(main())
