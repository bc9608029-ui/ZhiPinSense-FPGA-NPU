#!/usr/bin/env python3
"""Deterministically package the h5-based fix10prep1 clean-IQ diagnostic hotfix."""

from __future__ import annotations

import gzip
import hashlib
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent.parent
H5_BASE = Path(os.environ.get(
    "FIX10PREP1_H5_BASE",
    str(WORKSPACE / "fix9r2g1_work" /
        "sdr_rml23_live_board_package_iq_rf_loopback_fix9r2g1"),
)).resolve()
DIST = ROOT / "dist"

PATCH_TOP = "sdr_rml23_live_clean_iq_fix10prep1_patch"
FULL_TOP = "sdr_rml23_live_board_package_clean_iq_fix10prep1"
PATCH_TAR = DIST / (PATCH_TOP + ".tar.gz")
FULL_TAR = DIST / (FULL_TOP + ".tar.gz")
PATCH_SUMS = "FIX10PREP1_CLEAN_PATCH_SHA256SUMS.txt"
FULL_SUMS = "SHA256SUMS.txt"

PATCH_FILES = sorted([
    "board_package/board_gate9_full_chain_rml23.cpp",
    "board_package/gate9_phase.hpp",
    "board_package/iq_clean_baseline.hpp",
    "board_package/iq_clean_diagnostic_fix10prep1.hpp",
    "board_package/iq_clean_iq_23class_fix10.hpp",
    "docs/M29_RML23_FIX10PREP1_CLEAN_INPUT_BACKEND_AUDIT.md",
    "host_tests/build_host_tests.sh",
    "host_tests/run_tests.sh",
    "host_tests/test_clean_iq_23class_fix10.cpp",
    "scripts/analyze_clean_board_tensor_backend.py",
    "scripts/gen_generated_clean_23.py",
    "scripts/package_clean_iq_fix10prep1.py",
    "scripts/predict_clean_baseline.py",
])

EXCLUDED_DIRS = {"dist", "bin", "__pycache__", ".git", ".pytest_cache"}
PROTECTED_DIRS = ["model_rml23", "model_12class", "contracts", "deployment_golden"]
PROTECTED_FILES = ["board_package/iq_rf_sync_recovery.hpp"]
INCLUDE_RE = re.compile(r'^\s*#\s*include\s*"([^"]+)"')


def die(message: str) -> None:
    raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def selected_files(root: Path) -> list[str]:
    result: list[str] = []
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for filename in sorted(filenames):
            path = Path(directory) / filename
            rel = path.relative_to(root).as_posix()
            if rel.endswith((".pyc", ".pyo")):
                continue
            result.append(rel)
    return sorted(result)


def copy_file(source_root: Path, destination_root: Path, rel: str) -> None:
    source = source_root / rel
    if not source.is_file():
        die("missing package file: %s" % rel)
    destination = destination_root / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(0o755 if rel.endswith(".sh") else 0o644)


def write_sums(stage: Path, name: str) -> int:
    rels = [rel for rel in selected_files(stage) if rel != name]
    lines = ["%s *%s\n" % (sha256_file(stage / rel), rel) for rel in rels]
    (stage / name).write_text("".join(lines), encoding="utf-8", newline="\n")
    (stage / name).chmod(0o644)
    return len(rels)


def compare_tree_contract() -> tuple[int, int, int]:
    if not H5_BASE.is_dir():
        die("authoritative h5 base not found: %s" % H5_BASE)
    base_files = set(selected_files(H5_BASE))
    work_files = set(selected_files(ROOT))
    allowed = set(PATCH_FILES)
    changed: list[str] = []
    added: list[str] = []
    removed: list[str] = []
    for rel in sorted(base_files | work_files):
        if rel not in base_files:
            added.append(rel)
        elif rel not in work_files:
            removed.append(rel)
        elif sha256_file(H5_BASE / rel) != sha256_file(ROOT / rel):
            changed.append(rel)
    actual = set(added + changed + removed)
    if removed:
        die("h5 files removed: %s" % ", ".join(removed))
    unexpected = sorted(actual - allowed)
    missing = sorted(allowed - actual)
    if unexpected:
        die("unexpected worktree changes: %s" % ", ".join(unexpected))
    if missing:
        die("declared patch files not changed/new: %s" % ", ".join(missing))
    return len(base_files), len(changed), len(added)


def verify_protected() -> None:
    for rel in PROTECTED_FILES:
        if sha256_file(ROOT / rel) != sha256_file(H5_BASE / rel):
            die("protected file changed: %s" % rel)
    for dirname in PROTECTED_DIRS:
        base = H5_BASE / dirname
        work = ROOT / dirname
        if not base.exists() and not work.exists():
            continue
        base_files = selected_files(base)
        work_files = selected_files(work)
        if base_files != work_files:
            die("protected directory membership changed: %s" % dirname)
        for rel in base_files:
            if sha256_file(base / rel) != sha256_file(work / rel):
                die("protected content changed: %s/%s" % (dirname, rel))


def resolve_local_include(source: Path, include: str) -> Path | None:
    candidates = [
        source.parent / include,
        ROOT / "board_package" / include,
        ROOT / "sdr_adapter" / include,
        ROOT / "host_tests" / include,
        ROOT / "ui_sw" / include,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def dependency_closure() -> int:
    queue = [ROOT / rel for rel in PATCH_FILES if rel.endswith((".cpp", ".hpp", ".h"))]
    seen: set[Path] = set()
    unresolved: list[str] = []
    while queue:
        source = queue.pop()
        source = source.resolve()
        if source in seen:
            continue
        seen.add(source)
        text = source.read_text(encoding="utf-8")
        for line in text.splitlines():
            match = INCLUDE_RE.match(line)
            if not match:
                continue
            include = match.group(1)
            resolved = resolve_local_include(source, include)
            if resolved is None:
                # Generated/config headers and external SDK headers use <>; every
                # quoted include in this tree is required to resolve locally.
                unresolved.append("%s -> %s" % (source.relative_to(ROOT), include))
            elif ROOT in resolved.parents:
                queue.append(resolved)
    if unresolved:
        die("dependency closure failed: " + "; ".join(sorted(unresolved)))
    return len(seen)


def create_tar(stage: Path, destination: Path) -> None:
    raw = destination.with_suffix(destination.suffix + ".tmp.tar")
    top = stage.name
    entries: list[tuple[str, bool]] = [("", True)]
    for directory, dirnames, filenames in os.walk(stage):
        dirnames.sort()
        filenames.sort()
        for name in dirnames:
            rel = (Path(directory) / name).relative_to(stage).as_posix()
            entries.append((rel, True))
        for name in filenames:
            rel = (Path(directory) / name).relative_to(stage).as_posix()
            entries.append((rel, False))
    with tarfile.open(raw, "w", format=tarfile.GNU_FORMAT) as archive:
        for rel, is_dir in sorted(entries):
            path = stage if not rel else stage / rel
            arcname = top if not rel else top + "/" + rel
            info = archive.gettarinfo(str(path), arcname=arcname)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o755 if is_dir or rel.endswith(".sh") else 0o644
            if is_dir:
                archive.addfile(info)
            else:
                with path.open("rb") as stream:
                    archive.addfile(info, stream)
    with raw.open("rb") as source, destination.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output,
                           compresslevel=9, mtime=0) as compressor:
            shutil.copyfileobj(source, compressor)
    raw.unlink()


def verify_tar(path: Path, sums_name: str, expected_top: str) -> tuple[int, int]:
    with tempfile.TemporaryDirectory(prefix="fix10prep1_clean_verify_") as temp:
        temp_path = Path(temp)
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                pure = Path(member.name)
                if pure.is_absolute() or ".." in pure.parts:
                    die("unsafe tar member: %s" % member.name)
            archive.extractall(temp_path)
        root = temp_path / expected_top
        lines = (root / sums_name).read_text(encoding="utf-8").splitlines()
        ok = 0
        for line in lines:
            digest, marker, rel = line.partition(" *")
            if marker != " *" or sha256_file(root / rel) != digest:
                die("independent extraction hash mismatch: %s" % rel)
            ok += 1
        return ok, len(selected_files(root))


def make_stages(temp_root: Path) -> tuple[Path, Path, int, int]:
    patch = temp_root / PATCH_TOP
    full = temp_root / FULL_TOP
    patch.mkdir()
    full.mkdir()
    for rel in PATCH_FILES:
        copy_file(ROOT, patch, rel)
    for rel in selected_files(ROOT):
        copy_file(ROOT, full, rel)
    patch_count = write_sums(patch, PATCH_SUMS)
    full_count = write_sums(full, FULL_SUMS)
    return patch, full, patch_count, full_count


def main() -> int:
    base_count, modified_count, added_count = compare_tree_contract()
    verify_protected()
    closure_count = dependency_closure()
    DIST.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="fix10prep1_clean_package_") as temp:
        patch, full, patch_count, full_count = make_stages(Path(temp))
        create_tar(patch, PATCH_TAR)
        create_tar(full, FULL_TAR)

    first_patch = sha256_file(PATCH_TAR)
    first_full = sha256_file(FULL_TAR)
    with tempfile.TemporaryDirectory(prefix="fix10prep1_clean_repeat_") as temp:
        patch, full, _, _ = make_stages(Path(temp))
        repeat_patch = Path(temp) / "patch.tar.gz"
        repeat_full = Path(temp) / "full.tar.gz"
        create_tar(patch, repeat_patch)
        create_tar(full, repeat_full)
        if sha256_file(repeat_patch) != first_patch or sha256_file(repeat_full) != first_full:
            die("deterministic two-run package SHA mismatch")

    patch_verified, patch_members = verify_tar(PATCH_TAR, PATCH_SUMS, PATCH_TOP)
    full_verified, full_members = verify_tar(FULL_TAR, FULL_SUMS, FULL_TOP)
    (DIST / (PATCH_TAR.name + ".sha256")).write_text(
        "%s *%s\n" % (first_patch, PATCH_TAR.name), encoding="ascii")
    (DIST / (FULL_TAR.name + ".sha256")).write_text(
        "%s *%s\n" % (first_full, FULL_TAR.name), encoding="ascii")

    print("FIX10PREP1_CLEAN_PACKAGE result=PASS base_files=%d modified=%d added=%d "
          "dependency_files=%d" %
          (base_count, modified_count, added_count, closure_count))
    print("PATCH path=%s content_files=%d tar_members=%d verified=%d bytes=%d sha256=%s" %
          (PATCH_TAR, patch_count, patch_members, patch_verified,
           PATCH_TAR.stat().st_size, first_patch))
    print("FULL path=%s content_files=%d tar_members=%d verified=%d bytes=%d sha256=%s" %
          (FULL_TAR, full_count, full_members, full_verified,
           FULL_TAR.stat().st_size, first_full))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
