#!/usr/bin/env python3
"""Independent unpack + closure verification for the AC-integration candidate.

Run OUTSIDE the tree (so the check is independent of the source files)::

    python3 -I scripts/verify_ac_package.py \
        --archive dist/rml24_ac_integration_candidate.tar.gz \
        --out /tmp/ac_verify

Stage 1 (always): unpack to a clean dir, verify every manifest SHA, verify both
start entries' identity, and import the 5 self-contained ``multisignal_*``
modules (numpy + stdlib only) in an isolated subprocess.

Stage 2 (with ``--base local_base``): simulate ``install_overlay.sh`` base+overlay
on the host, then run ``preflight_deploy.py`` against the merged tree AND
statically resolve each start entry's full import closure (BASE deps now resolve).

Exit codes: 0 = all checks pass; 1 = unpack/SHA/closure failure; 4 = usage.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

MANIFEST_NAME = "SHA256SUMS_AC.txt"
# sys.path dirs the two start entries create (standalone_receiver*.py lines 31-33).
RESOLVE_DIRS = ("runtime", "recovery", "board_runtime")

# C-line dev-tree shims that never resolve in a flat deployment (documented
# fallbacks / aliases only).  Their absence is correct.
DEV_SHIMS = {"src", "reference", "integration"}

START_ENTRIES = {
    "overlay/rml24_final/board_runtime/standalone_receiver.py":
        "4d35cf5e27f26d6c1bc06f2dbf961b139931b0998ca3995ce47685af38058293",
    "overlay/rml24_final/board_runtime/standalone_receiver_multisignal.py":
        "35f8dd6c777136052dc8769f2d532608d07f7e98c08d119860a3c8418d4e3939",
}

MULTISIGNAL_MODULES = (
    "multisignal_contracts",
    "multisignal_tracker",
    "multisignal_psd",
    "multisignal_scan_adapter",
    "multisignal_receiver_entry",
)

# ReceiverEntry surface the entry driver and offline parity tests rely on.
RECEIVER_ENTRY_METHODS = (
    "step", "_step_fixed", "_classify_one", "_measure_and_update",
    "_emit_state", "_save_capture_fixed", "_save_capture_scan",
    "_write_record", "_write_status", "run",
)

IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)",
    re.MULTILINE,
)


def sha256_of(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def unpack(archive: Path, out: Path) -> None:
    if out.exists():
        if any(out.iterdir()):
            raise SystemExit(f"VERIFY result=FAIL rc=1 reason=out_dir_not_empty {out}")
    else:
        out.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(out, filter="data")


def verify_manifest(root: Path) -> None:
    manifest = root / MANIFEST_NAME
    if not manifest.is_file():
        raise SystemExit(f"VERIFY result=FAIL rc=1 reason=missing_manifest {manifest}")
    listed: dict[str, str] = {}
    for lineno, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise SystemExit(f"VERIFY result=FAIL rc=1 reason=bad_manifest_line {lineno}: {line!r}")
        digest, rel = parts
        listed[rel] = digest.lower()
    missing = [rel for rel in listed if not (root / rel).is_file()]
    mismatch = [rel for rel, want in listed.items()
                if (root / rel).is_file() and sha256_of(root / rel) != want]
    if missing or mismatch:
        for rel in missing:
            print(f"VERIFY MISSING {rel}")
        for rel in mismatch:
            print(f"VERIFY SHA_MISMATCH {rel}")
        raise SystemExit("VERIFY result=FAIL rc=1 reason=manifest_inconsistent")
    print(f"VERIFY manifest_ok files={len(listed)}")


def verify_start_entries(root: Path) -> None:
    for rel, want in START_ENTRIES.items():
        p = root / rel
        if not p.is_file():
            raise SystemExit(f"VERIFY result=FAIL rc=1 reason=missing_start_entry {rel}")
        got = sha256_of(p)
        if got != want:
            raise SystemExit(f"VERIFY result=FAIL rc=1 reason=start_entry_sha {rel} want={want} got={got}")
        print(f"VERIFY start_entry_ok {rel} sha={got[:16]}...")


def verify_multisignal_import(root: Path) -> None:
    runtime = root / "overlay" / "rml24_final" / "runtime"
    probe = (
        "import sys, importlib\n"
        f"sys.path.insert(0, {str(runtime)!r})\n"
        "mods = " + repr(list(MULTISIGNAL_MODULES)) + "\n"
        "for m in mods:\n"
        "    importlib.import_module(m)\n"
        "from multisignal_receiver_entry import ReceiverEntry\n"
        "missing = [a for a in " + repr(list(RECEIVER_ENTRY_METHODS)) + " if not hasattr(ReceiverEntry, a)]\n"
        "if missing:\n"
        "    raise SystemExit('missing ReceiverEntry methods: ' + repr(missing))\n"
        "print('VERIFY_MULTISIGNAL_IMPORT_OK methods=all_present')\n"
    )
    cp = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    if cp.returncode != 0:
        print(cp.stdout, end="")
        print(cp.stderr, end="", file=sys.stderr)
        raise SystemExit("VERIFY result=FAIL rc=1 reason=multisignal_import_probe")
    print(cp.stdout.strip())


def _imported_heads(text: str) -> list[str]:
    heads = []
    for m in IMPORT_RE.finditer(text):
        for part in m.group(1).split(","):
            name = part.strip()
            if name:
                heads.append(name.split(".")[0])
    return heads


def resolve_closure(rml24: Path, entry: Path, seen: set[str] | None = None) -> tuple[list[str], list[str]]:
    """Resolve an entry's project-internal imports against a deployed ``rml24_final`` dir."""
    if seen is None:
        seen = set()
    ok: list[str] = []
    unresolved: list[str] = []
    for head in _imported_heads(entry.read_text(encoding="utf-8")):
        if head in seen or head in DEV_SHIMS:
            continue
        target = None
        for d in RESOLVE_DIRS:
            cand = rml24 / d / f"{head}.py"
            if cand.is_file():
                target = cand
                break
        if target is not None:
            seen.add(head)
            ok.append(head)
            sub_ok, sub_unresolved = resolve_closure(rml24, target, seen)
            ok.extend(sub_ok)
            unresolved.extend(sub_unresolved)
        elif importlib.util.find_spec(head) is None:
            unresolved.append(head)
    return ok, unresolved


# The 5 BASE-sourced runtime deps (UNVERIFIED_DEPS in preflight_deploy.py).
PREFLIGHT_BASE_DEPS = (
    "rml24_final/runtime/standalone_control.py",
    "rml24_final/runtime/radio_tuning.py",
    "rml24_final/runtime/scan_runtime.py",
    "rml24_final/board_runtime/rml24_dualmode_receiver_centered_v2.py",
    "rml24_final/runtime/mode_control_server.py",
)


def _run_preflight(preflight: Path, tree: Path, expect: Path | None = None):
    cmd = [sys.executable, str(preflight), "--tree", str(tree)]
    if expect is not None:
        cmd += ["--expect", str(expect)]
    return subprocess.run(cmd, capture_output=True, text=True)


def verify_preflight_modes(merged: Path, preflight: Path) -> None:
    """Exercise the REAL preflight (not a fixture) across every exit contract."""
    tmp = Path(tempfile.mkdtemp(prefix="ac_pfmodes_"))
    try:
        # (0) offline-only: no --expect -> rc=0 PASS_OFFLINE_ONLY (NOT acceptance)
        cp = _run_preflight(preflight, merged)
        if cp.returncode != 0 or "result=PASS_OFFLINE_ONLY" not in cp.stdout:
            raise SystemExit(f"VERIFY result=FAIL rc=1 reason=preflight_offline_only\n{cp.stdout}{cp.stderr}")
        print("VERIFY preflight_offline_only PASS_OFFLINE_ONLY rc=0")

        # (1) strict pass: --expect confirming all 5 BASE deps -> rc=0 PASS_STRICT
        expect = tmp / "expect_full.txt"
        rows = [f"{sha256_of(merged / rel)}  {rel}" for rel in PREFLIGHT_BASE_DEPS]
        expect.write_text("\n".join(rows) + "\n", encoding="utf-8")
        cp = _run_preflight(preflight, merged, expect)
        if cp.returncode != 0 or "result=PASS_STRICT" not in cp.stdout:
            raise SystemExit(f"VERIFY result=FAIL rc=1 reason=preflight_strict_pass\n{cp.stdout}{cp.stderr}")
        print("VERIFY preflight_strict PASS_STRICT rc=0 (all 5 BASE deps confirmed)")

        # (2) strict incomplete: only 4 of 5 deps -> rc=3 expect_incomplete
        inc = tmp / "expect_incomplete.txt"
        inc.write_text("\n".join(rows[:4]) + "\n", encoding="utf-8")
        cp = _run_preflight(preflight, merged, inc)
        if cp.returncode != 3 or "expect_incomplete" not in cp.stdout:
            raise SystemExit(f"VERIFY result=FAIL rc=1 reason=preflight_expect_incomplete rc={cp.returncode}\n{cp.stdout}{cp.stderr}")
        print("VERIFY preflight_incomplete rc=3 expect_incomplete")

        # (3) expect mismatch: one dep wrong SHA -> rc=3 expect_mismatch
        mis = tmp / "expect_mismatch.txt"
        bad_rows = list(rows)
        bad_rows[0] = ("0" * 64) + "  " + PREFLIGHT_BASE_DEPS[0]
        mis.write_text("\n".join(bad_rows) + "\n", encoding="utf-8")
        cp = _run_preflight(preflight, merged, mis)
        if cp.returncode != 3 or "expect_mismatch" not in cp.stdout:
            raise SystemExit(f"VERIFY result=FAIL rc=1 reason=preflight_expect_mismatch rc={cp.returncode}\n{cp.stdout}{cp.stderr}")
        print("VERIFY preflight_mismatch rc=3 expect_mismatch")

        # (4) known-frozen drift -> rc=2 known_sha_mismatch
        clone = tmp / "clone_drift"
        shutil.copytree(merged, clone)
        victim = clone / "rml24_final/runtime/multisignal_contracts.py"
        victim.write_bytes(victim.read_bytes() + b"\n# drift\n")
        cp = _run_preflight(preflight, clone)
        if cp.returncode != 2 or "known_sha_mismatch" not in cp.stdout:
            raise SystemExit(f"VERIFY result=FAIL rc=1 reason=preflight_known_drift rc={cp.returncode}\n{cp.stdout}{cp.stderr}")
        print("VERIFY preflight_known_drift rc=2 known_sha_mismatch")

        # (5) missing required file -> rc=1 missing_file
        clone2 = tmp / "clone_missing"
        shutil.copytree(merged, clone2)
        (clone2 / "rml24_final/recovery/candidate_two_dc.py").unlink()
        cp = _run_preflight(preflight, clone2)
        if cp.returncode != 1 or "missing_file" not in cp.stdout:
            raise SystemExit(f"VERIFY result=FAIL rc=1 reason=preflight_missing rc={cp.returncode}\n{cp.stdout}{cp.stderr}")
        print("VERIFY preflight_missing rc=1 missing_file")

        # (6) usage: tree lacking rml24_final/board_package -> rc=4
        bogus = tmp / "bogus"
        bogus.mkdir()
        cp = _run_preflight(preflight, bogus)
        if cp.returncode != 4:
            raise SystemExit(f"VERIFY result=FAIL rc=1 reason=preflight_usage rc={cp.returncode}\n{cp.stdout}{cp.stderr}")
        print("VERIFY preflight_usage rc=4")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def verify_merged_preflight(base: Path, overlay: Path) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ac_preflight_"))
    try:
        merged = tmp / "merged"
        rml24 = merged / "rml24_final"
        # local_base/{runtime,recovery,board_runtime} -> rml24_final/{...}
        for d in RESOLVE_DIRS:
            shutil.copytree(base / d, rml24 / d)
        # overlay/... -> merged/...  (overlay/rml24_final merges with the base deps)
        shutil.copytree(overlay, merged, dirs_exist_ok=True)

        # (a) dependency-closure resolution against the merged (deployed) tree.
        for rel in START_ENTRIES:
            entry = merged / rel.removeprefix("overlay/")
            ok, unresolved = resolve_closure(rml24, entry)
            print(f"VERIFY closure {rel} resolved={len(ok)} unresolved={unresolved or 'none'}")
            if unresolved:
                raise SystemExit(
                    f"VERIFY result=FAIL rc=1 reason=unresolved_imports {rel}: {unresolved}")

        # (b) A-line dependency precheck (existence + frozen SHA) on the merged tree.
        preflight = Path(__file__).resolve().parent / "preflight_deploy.py"
        cp = subprocess.run(
            [sys.executable, str(preflight), "--tree", str(merged)],
            capture_output=True, text=True,
        )
        print(cp.stdout, end="")
        if cp.returncode != 0:
            print(cp.stderr, end="", file=sys.stderr)
            raise SystemExit(f"VERIFY result=FAIL rc={cp.returncode} reason=merged_preflight")
        print("VERIFY merged_preflight_ok (base+overlay, host-simulated)")

        # (c) real-preflight exit contract: strict pass + all failure modes.
        verify_preflight_modes(merged, preflight)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--base", help="optional local_base dir for host-simulated merged preflight")
    args = ap.parse_args()

    archive = Path(args.archive)
    out = Path(args.out)
    if not archive.is_file():
        print(f"VERIFY result=USAGE rc=4 reason=missing_archive {archive}", file=sys.stderr)
        return 4

    unpack(archive, out)
    verify_manifest(out)
    verify_start_entries(out)
    verify_multisignal_import(out)
    if args.base:
        verify_merged_preflight(Path(args.base), out / "overlay")
    print("VERIFY result=PASS rc=0 independent_unpack_verify_complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
