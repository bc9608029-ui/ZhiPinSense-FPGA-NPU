#!/usr/bin/env python3
"""Deployment pre-flight for the RML24 main-chain candidate (fail-closed).

Run ON THE BOARD, after `install_overlay.sh --base ... --out $TEST`, BEFORE build/RF:

    python3 "$TEST/rml24_final/../scripts/preflight_deploy.py" --tree "$TEST"
    #   -- but preflight_deploy.py ships in candidate/scripts/, so from the
    #   uploaded DELIVERY dir use:
    python3 "$DELIVERY/scripts/preflight_deploy.py" --tree "$TEST"

What it checks (exit code semantics):
  rc=0  all hard checks pass; UNVERIFIED deps are REPORTED (not auto-accepted)
  rc=1  a required file in the dependency closure is MISSING
  rc=2  a KNOWN-frozen file SHA MISMATCHES
  rc=3  an --expect manifest entry MISMATCHES (board-supplied frozen list)
  rc=4  usage error

The four BASE-sourced runtime deps (standalone_control.py, radio_tuning.py,
scan_runtime.py, rml24_dualmode_receiver_centered_v2.py) are NOT frozen in this
offline delivery. This script NEVER treats a local copy as the trusted board
baseline and NEVER auto-accepts an arbitrary SHA: without --expect it only
verifies their EXISTENCE and PRINTS the measured SHA marked UNVERIFIED_NEED_BOARD_CHECK.
With --expect (a `sha256  relpath` file you build from board measurements and
review) it verifies them strictly and fails on any mismatch.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

# KNOWN-frozen files in the deployed tree (overlay + runtime-checked BASE files).
# These SHAs are authoritative for this round and are hard-failed on mismatch.
KNOWN_FROZEN = {
    "rml24_final/board_runtime/standalone_receiver.py":
        "4d35cf5e27f26d6c1bc06f2dbf961b139931b0998ca3995ce47685af38058293",
    "rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py":
        "efe066db23799d9bd637ead702e2b70b2fefcdb492bdce3d3c80ee67184e4d0a",
    "rml24_final/board_runtime/repeat_mean_candidate.py":
        "1e837d42485ce717023b580918773f9f53c3095ab3c4f2870321bd58ebd0bdde",
    "rml24_final/runtime/receiver_core.py":
        "cb529824a80e9fa2aea6aaa31375c8d560f117c36b9644862cb459f6c39cd79a",
    "rml24_final/runtime/scan_lock_policy.py":
        "912f2e24a0cb50768eb8bcdcfc552a8a57082900c85ec4c8485ffb264c13f320",
    "rml24_final/runtime/ui_event.py":
        "990d75fe288ecd50a41743d5f6fa451171b435505015278d3a757c961b7ec43d",
    "rml24_final/recovery/candidate_two_dc.py":
        "e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a",
}

# BASE-sourced deps NOT frozen in this offline delivery.  Existence is required
# (the run entry imports them); identity is board-verified only (never auto-trusted).
UNVERIFIED_DEPS = [
    "rml24_final/runtime/standalone_control.py",
    "rml24_final/runtime/radio_tuning.py",
    "rml24_final/runtime/scan_runtime.py",
    "rml24_final/board_runtime/rml24_dualmode_receiver_centered_v2.py",
]

# All files in the deployed dependency closure must exist.
REQUIRED = sorted(set(KNOWN_FROZEN) | set(UNVERIFIED_DEPS))


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_expect(path: Path) -> dict[str, str]:
    """Parse a `sha256  relpath` manifest (like sha256sum output)."""
    expect: dict[str, str] = {}
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            raise SystemExit(f"PREFLIGHT usage: bad expect line {lineno}: {line!r}")
        digest, rel = parts
        expect[rel] = digest.lower()
    return expect


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True, help="deployed test tree (install_overlay.sh --out)")
    ap.add_argument("--expect", help="optional board-supplied `sha256  relpath` frozen list")
    args = ap.parse_args()

    tree = Path(args.tree)
    if not (tree / "rml24_final").is_dir() or not (tree / "board_package").is_dir():
        print(f"PREFLIGHT result=USAGE error=invalid tree (missing rml24_final/board_package): {tree}", file=sys.stderr)
        return 4

    expect = load_expect(Path(args.expect)) if args.expect else {}

    missing = [rel for rel in REQUIRED if not (tree / rel).is_file()]
    if missing:
        for rel in missing:
            print(f"PREFLIGHT MISSING {rel}")
        print(f"PREFLIGHT result=FAIL rc=1 reason=missing_file count={len(missing)}")
        return 1

    mismatch = []
    for rel, want in sorted(KNOWN_FROZEN.items()):
        got = sha256_of(tree / rel)
        if got.lower() != want.lower():
            mismatch.append((rel, want, got))
    if mismatch:
        for rel, want, got in mismatch:
            print(f"PREFLIGHT KNOWN_SHA_MISMATCH {rel} want={want} got={got}")
        print(f"PREFLIGHT result=FAIL rc=2 reason=known_sha_mismatch count={len(mismatch)}")
        return 2

    unverified = []
    for rel in UNVERIFIED_DEPS:
        got = sha256_of(tree / rel)
        status = "UNVERIFIED_NEED_BOARD_CHECK"
        if rel in expect:
            if got.lower() != expect[rel].lower():
                print(f"PREFLIGHT EXPECT_MISMATCH {rel} want={expect[rel]} got={got}")
                print("PREFLIGHT result=FAIL rc=3 reason=expect_mismatch")
                return 3
            status = "EXPECT_OK"
        unverified.append((rel, got, status))

    # Verified known-frozen files are reported for the record.
    for rel in sorted(KNOWN_FROZEN):
        print(f"PREFLIGHT KNOWN_OK {rel} sha={sha256_of(tree / rel)[:16]}...")
    for rel, got, status in unverified:
        print(f"PREFLIGHT {status} {rel} sha={got}")
    if any(status == "UNVERIFIED_NEED_BOARD_CHECK" for _, _, status in unverified):
        print("PREFLIGHT result=PASS_WITH_UNVERIFIED rc=0 note=4 BASE deps need board sha256sum confirmation (see DEPENDENCY_IDENTITY.md); do not proceed to RF until confirmed")
    else:
        print("PREFLIGHT result=PASS rc=0 all_identity_checks_pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
