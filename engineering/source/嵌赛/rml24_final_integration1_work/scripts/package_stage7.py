#!/usr/bin/env python3
"""Build deterministic, truth-isolated board and PC Stage-7 packages."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "amr_rescue_gmsk_candidate_20261026"
DATASET = SOURCE / "validation_seed5100000"
UI_BASE = ROOT.parent / "fix10class24_waterfall1_work" / "sdr_rml24_fix10class24_waterfall1"
DIST = ROOT / "dist"
MTIME = 315532800


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree_files(directories: tuple[str, ...]) -> list[tuple[str, bytes, int]]:
    values = []
    for directory in directories:
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".gz"}:
                mode = 0o755 if path.suffix in {".py", ".sh"} else 0o644
                values.append((path.relative_to(ROOT).as_posix(), path.read_bytes(), mode))
    values.append(("README.md", (ROOT / "README.md").read_bytes(), 0o644))
    return sorted(values)


def ui_base_files() -> list[tuple[str, bytes, int]]:
    """Vendor only the tested UI build dependencies, never models/results."""
    values = []
    for directory in ("board_package", "sdr_adapter", "ui_sw"):
        base = UI_BASE / directory
        if not base.is_dir():
            raise SystemExit(f"missing validated UI base directory: {base}")
        for path in base.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".gz"}:
                mode = 0o755 if path.suffix in {".py", ".sh"} else 0o644
                rel = path.relative_to(UI_BASE).as_posix()
                values.append((f"base_ui/{rel}", path.read_bytes(), mode))
    return sorted(values)


def archive_bytes(prefix: str, members: list[tuple[str, bytes, int]]) -> bytes:
    sums = "".join(f"{sha(data)}  {name}\n" for name, data, _ in members).encode("ascii")
    all_members = members + [("SHA256SUMS.txt", sums, 0o644)]
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name, data, mode in all_members:
            info = tarfile.TarInfo(f"{prefix}/{name}")
            info.size = len(data)
            info.mode = mode
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = MTIME
            tar.addfile(info, io.BytesIO(data))
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0, compresslevel=9) as stream:
        stream.write(raw.getvalue())
    return output.getvalue()


def build_one(filename: str, prefix: str, members: list[tuple[str, bytes, int]]) -> tuple[str, int]:
    first = archive_bytes(prefix, members)
    second = archive_bytes(prefix, members)
    if first != second:
        raise RuntimeError(f"non-deterministic archive {filename}")
    path = DIST / filename
    path.write_bytes(first)
    digest = sha(first)
    path.with_name(path.name + "_SHA256.txt").write_text(f"{digest}  {path.name}\n", encoding="ascii", newline="\n")
    return digest, len(first)


def main() -> int:
    DIST.mkdir(parents=True, exist_ok=True)
    board_members = tree_files(("board_runtime", "board_ui_overlay", "contract", "deploy", "docs", "recovery", "runtime"))
    board_members.extend(ui_base_files())
    board_members.sort()
    forbidden = ("expected", "private", "selftest_manifest", "evidence/", "pc_runtime/")
    leaks = [name for name, _, _ in board_members if any(token in name.lower() for token in forbidden)]
    if leaks:
        raise SystemExit(f"board truth-isolation audit failed: {leaks}")

    manifest_path = ROOT / "pc_runtime" / "selftest_manifest_240.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = manifest_data["records"]
    if len(rows) != 240:
        raise SystemExit("public TX manifest does not contain 240 rows")
    pc_members = [
        ("pc_runtime/rml24_final_tx.py", (ROOT / "pc_runtime" / "rml24_final_tx.py").read_bytes(), 0o755),
        ("pc_runtime/selftest_manifest_240.json", manifest_path.read_bytes(), 0o644),
        ("truth/expected_private.json", (DATASET / "expected_private.json").read_bytes(), 0o600),
        ("scripts/summarize_selftest.py", (ROOT / "scripts" / "summarize_selftest.py").read_bytes(), 0o755),
        ("scripts/score_stage7_run.py", (ROOT / "scripts" / "score_stage7_run.py").read_bytes(), 0o755),
    ]
    for row in rows:
        source = DATASET / row["file"]
        data = source.read_bytes()
        if sha(data) != row["source_sha256"]:
            raise SystemExit(f"dataset SHA mismatch: {row['file']}")
        pc_members.append((f"dataset/{row['file']}", data, 0o644))
    pc_members.sort()

    board_sha, board_size = build_one(
        "rml24_final_stage7_board_overlay.tar.gz",
        "rml24_final_stage7_board_overlay",
        board_members,
    )
    pc_sha, pc_size = build_one(
        "rml24_final_stage7_pc_selftest.tar.gz",
        "rml24_final_stage7_pc_selftest",
        pc_members,
    )
    print(
        "RML24_FINAL_STAGE7_PACKAGES result=PASS "
        f"board_sha={board_sha} board_bytes={board_size} board_files={len(board_members) + 1} "
        f"pc_sha={pc_sha} pc_bytes={pc_size} pc_files={len(pc_members) + 1} waveform_files=240"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
