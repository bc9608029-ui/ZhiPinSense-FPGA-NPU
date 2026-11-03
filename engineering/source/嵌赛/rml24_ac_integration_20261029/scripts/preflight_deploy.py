#!/usr/bin/env python3
"""Deployment pre-flight for the RML24 main-chain candidate (fail-closed).

Run ON THE BOARD, after `install_overlay.sh --base ... --out $TEST`, BEFORE build/RF:

    python3 "$TEST/rml24_final/../scripts/preflight_deploy.py" --tree "$TEST"
    #   -- but preflight_deploy.py ships in candidate/scripts/, so from the
    #   uploaded DELIVERY dir use:
    python3 "$DELIVERY/scripts/preflight_deploy.py" --tree "$TEST"

What it checks (exit code semantics):
  rc=0  offline-only: 13 frozen SHAs OK + 5 BASE deps EXIST (identity NOT confirmed)
        -> result=PASS_OFFLINE_ONLY dependency_identity_verified=NO rf_forbidden=YES
        strict (--expect): all 5 BASE deps confirmed -> PASS_STRICT dependency_identity_verified=YES
  rc=1  a required file in the dependency closure is MISSING
  rc=2  a KNOWN-frozen file SHA MISMATCHES
  rc=3  an --expect entry MISMATCHES, OR strict --expect is INCOMPLETE (a BASE dep missing)
  rc=4  usage error

The five BASE-sourced runtime deps (standalone_control.py, radio_tuning.py,
scan_runtime.py, rml24_dualmode_receiver_centered_v2.py, mode_control_server.py)
are NOT frozen in this offline delivery. This script NEVER treats a local copy as the trusted board
baseline and NEVER auto-accepts an arbitrary SHA. PASS_OFFLINE_ONLY (no --expect)
is NOT full acceptance and MUST NOT gate RF: it only verifies their EXISTENCE and
PRINTS the measured SHA marked UNVERIFIED_NEED_BOARD_CHECK. Strict mode
(--expect a `sha256  relpath` file you build from board measurements and review)
requires ALL five BASE deps to be present AND match; it fails on any mismatch or
any missing entry, and only then reports PASS_STRICT dependency_identity_verified=YES.
That flag means DEPENDENCY-IDENTITY acceptance ONLY -- it never implies board
build/display/touch/RF acceptance.
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
    # AC-integration candidate entry (multi-signal).  All overlay-sourced,
    # authoritative for this round.
    "rml24_final/board_runtime/standalone_receiver_multisignal.py":
        "35f8dd6c777136052dc8769f2d532608d07f7e98c08d119860a3c8418d4e3939",
    "rml24_final/runtime/multisignal_contracts.py":
        "f23dd3401703f0e20378e22afa6db3b933884b310710e9a6e120c24218a981e3",
    "rml24_final/runtime/multisignal_tracker.py":
        "7af0ff2655fc03f19ec2ff79c114b54f6a6814c16c2f36569700a58849d73cca",
    "rml24_final/runtime/multisignal_psd.py":
        "4dba4f7e77c2dc8c97d8af7c175fa908d8771a2a5586cd212a1965924a043a7b",
    "rml24_final/runtime/multisignal_scan_adapter.py":
        "95723baedccfbb96e75ca1946cedde084ef91d3903b43b5a8ff6e2439cb13940",
    "rml24_final/runtime/multisignal_receiver_entry.py":
        "125590e7261e583625da08b3c66a900d244c62cf0ab64d2ae4121293aaf8a7a4",
}

# BASE-sourced deps NOT frozen in this offline delivery.  Existence is required
# (the run entry imports them); identity is board-verified only (never auto-trusted).
UNVERIFIED_DEPS = [
    "rml24_final/runtime/standalone_control.py",
    "rml24_final/runtime/radio_tuning.py",
    "rml24_final/runtime/scan_runtime.py",
    "rml24_final/board_runtime/rml24_dualmode_receiver_centered_v2.py",
    # 9th BASE dep: rml24_dualmode_receiver_centered_v2 imports it transitively
    # (previously undocumented).  Board-verified only, never auto-trusted.
    "rml24_final/runtime/mode_control_server.py",
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

    strict = args.expect is not None
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

    expect_missing = []
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
        else:
            # Strict mode needs every BASE dep confirmed, so record what's absent.
            expect_missing.append(rel)
        unverified.append((rel, got, status))

    # Verified known-frozen files are reported for the record.
    for rel in sorted(KNOWN_FROZEN):
        print(f"PREFLIGHT KNOWN_OK {rel} sha={sha256_of(tree / rel)[:16]}...")
    for rel, got, status in unverified:
        print(f"PREFLIGHT {status} {rel} sha={got}")

    if strict:
        # Strict acceptance gate: --expect must confirm ALL five BASE deps.
        if expect_missing:
            for rel in expect_missing:
                print(f"PREFLIGHT EXPECT_MISSING {rel} (strict mode requires all 5 BASE deps)")
            print(f"PREFLIGHT result=FAIL rc=3 reason=expect_incomplete missing={len(expect_missing)} "
                  f"(strict --expect must confirm all 5 BASE deps before RF)")
            return 3
        print("PREFLIGHT result=PASS_STRICT rc=0 dependency_identity_verified=YES "
              "(13 frozen + 5 BASE deps all confirmed; dependency-identity acceptance ONLY, "
              "NOT board build/RF acceptance)")
    else:
        print("PREFLIGHT result=PASS_OFFLINE_ONLY rc=0 dependency_identity_verified=NO rf_forbidden=YES "
              "note=5 BASE deps unconfirmed; collect+compare identity only, do NOT proceed to RF "
              "until strict --expect passes (see DEPENDENCY_IDENTITY.md)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
