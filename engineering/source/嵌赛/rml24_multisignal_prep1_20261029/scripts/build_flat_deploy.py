#!/usr/bin/env python3
"""Build the FLAT deployment tree for the board RX runtime (C1).

The C-line dev package ``src/`` uses relative imports (``from . import contracts``).
The board entry ``standalone_receiver.py`` loads its runtime modules from a flat
directory (already on sys.path), so a single-file copy of ``tracker.py`` would fail
on ``from . import contracts``.  This generator resolves that by emitting a flat
module per source file with sibling absolute imports, together with a per-file SHA256
manifest -- the deployment structure chosen for C1 (flat, no package).

Emitted mapping (src -> flat):
  contracts      -> multisignal_contracts
  tracker        -> multisignal_tracker
  psd            -> multisignal_psd
  scan_adapter   -> multisignal_scan_adapter
  scoring        -> multisignal_scoring
  ui_model       -> multisignal_ui_model
  simulate       -> multisignal_simulate
  tx_synth       -> multisignal_tx_synth
  spectrum_audit -> multisignal_spectrum_audit
  receiver_entry -> multisignal_receiver_entry  (from integration/, C3+C5 entry)

Import rewrites:
  from . import X as Y  -> import multisignal_X as Y
  from . import X       -> import multisignal_X
  from .MOD import A    -> from multisignal_MOD import A

Usage:
  python scripts/build_flat_deploy.py --out deploy
Writes deploy/*.py + deploy/manifest.json + deploy/SHA256SUMS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

MODULES = {
    "contracts": "multisignal_contracts",
    "tracker": "multisignal_tracker",
    "psd": "multisignal_psd",
    "scan_adapter": "multisignal_scan_adapter",
    "scoring": "multisignal_scoring",
    "ui_model": "multisignal_ui_model",
    "simulate": "multisignal_simulate",
    "tx_synth": "multisignal_tx_synth",
    "spectrum_audit": "multisignal_spectrum_audit",
}

# Modules that live outside src/ (source path relative to ROOT -> flat name).
EXTRA_MODULES = {
    "integration/receiver_entry": "multisignal_receiver_entry",
}

_RE_FROM_PKG = re.compile(r"^from \. import (\w+)( as \w+)?\s*$")
_RE_FROM_MOD = re.compile(r"^from \.(\w+) import (.+)$")


def _rewrite(line: str) -> str:
    m = _RE_FROM_PKG.match(line)
    if m:
        alias = m.group(2) or ""
        return f"import {MODULES[m.group(1)]}{alias}\n"
    m = _RE_FROM_MOD.match(line)
    if m:
        return f"from {MODULES[m.group(1)]} import {m.group(2)}\n"
    return line


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=ROOT / "deploy")
    args = p.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []
    for src_name, flat_name in MODULES.items():
        src_path = SRC / f"{src_name}.py"
        if not src_path.exists():
            raise SystemExit(f"missing source {src_path}")
        lines = src_path.read_text(encoding="utf-8").splitlines(keepends=True)
        body = "".join(_rewrite(line) for line in lines)
        flat_path = out / f"{flat_name}.py"
        flat_path.write_text(body, encoding="utf-8")
        manifest.append({
            "flat": flat_path.name,
            "source": str(src_path.relative_to(ROOT)),
            "sha256": _sha256(flat_path),
        })

    for src_rel, flat_name in EXTRA_MODULES.items():
        src_path = ROOT / f"{src_rel}.py"
        if not src_path.exists():
            raise SystemExit(f"missing source {src_path}")
        lines = src_path.read_text(encoding="utf-8").splitlines(keepends=True)
        body = "".join(_rewrite(line) for line in lines)
        flat_path = out / f"{flat_name}.py"
        flat_path.write_text(body, encoding="utf-8")
        manifest.append({
            "flat": flat_path.name,
            "source": str(src_path.relative_to(ROOT)),
            "sha256": _sha256(flat_path),
        })

    manifest.sort(key=lambda d: d["flat"])
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sums = "".join(f"{d['sha256']}  {d['flat']}\n" for d in manifest)
    (out / "SHA256SUMS").write_text(sums, encoding="utf-8")
    print(f"flat deploy written to {out} ({len(manifest)} modules)")
    for d in manifest:
        print(f"  {d['flat']}  {d['sha256'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
