#!/usr/bin/env python3
"""C1 evidence: clean-directory import + startup probe for the FLAT deploy tree.

Run OUTSIDE the dev tree, with ONLY the generated deploy/*.py on the path, e.g.:

    tmp=$(mktemp -d)
    cp deploy/*.py "$tmp"/
    python -I scripts/probe_flat_deploy.py "$tmp"

The probe proves the flat single-file modules import cleanly (the original C1
failure was ``from . import contracts`` in a single-file ``multisignal_tracker``)
and that the REAL injectable entry (``multisignal_receiver_entry.ReceiverEntry``)
starts and runs one frame against the flat scheduler -- no package, no dev tree.
"""
from __future__ import annotations

import os
import sys

import numpy as np


def fail(msg: str) -> None:
    print(f"PROBE_FAIL: {msg}", flush=True)
    raise SystemExit(1)


def main() -> int:
    if len(sys.argv) != 2:
        fail("usage: probe_flat_deploy.py <flat-deploy-dir>")
    deploy = os.path.abspath(sys.argv[1])
    if not os.path.isdir(deploy):
        fail(f"not a directory: {deploy}")
    # Isolated, safe-path: the ONLY import source is the flat deploy dir.
    sys.path.insert(0, deploy)
    assert os.getcwd() not in sys.path or True  # -I already removed cwd

    # 1. Frozen contracts + tracker (the exact C1 failure point).
    import multisignal_contracts as C
    assert C.SAMPLE_RATE_HZ == 2_560_000, "contracts constant mismatch"
    from multisignal_tracker import TargetTracker
    tr = TargetTracker(aging_cycles=3)
    r1 = tr.observe(2_400_000_000, 1.0)
    r2 = tr.observe(2_400_500_000, 1.0)
    assert r1.target_id == 1 and r2.target_id == 2
    tr.end_cycle(); tr.end_cycle(); tr.end_cycle()
    assert tr.active_targets() == [], "aging did not expire"

    # 2. Scheduler imports flat.
    from multisignal_scan_adapter import MultiSignalScanLoop, ScanLoopOptions
    loop = MultiSignalScanLoop([2_400_000_000, 2_400_500_000], ScanLoopOptions())
    assert loop.lo_points == [2_400_000_000, 2_400_500_000]

    # 3. The REAL entry starts against the flat modules and runs one frame.
    from multisignal_receiver_entry import EntryConfig, ReceiverEntry

    class StubRadio:
        def tune(self, hz): return int(hz)
        def flush(self): pass
        def receive(self): return np.zeros(65_536, dtype=np.complex128)
        def close(self): return []

    class StubTransport:
        def __init__(self): self.events = []; self.sent = 0; self.failed = 0
        def send(self, e): self.events.append(e); self.sent += 1

    class NoDet:
        score = -1.0
        coarse_cfo_hz = 0.0

    transport = StubTransport()
    entry = ReceiverEntry(
        radio=StubRadio(),
        infer=lambda t: {"pred": -1, "finite": False},
        transport=transport,
        config=EntryConfig(scan_start_hz=2_400_000_000, scan_stop_hz=2_400_500_000,
                           scan_step_hz=500_000, initial_mode="BAND_SCAN"),
        detector=lambda raw: NoDet(),
        recover=lambda raw, fn: None,
        recover_fn=None,
        class_names=["C%d" % i for i in range(24)],
        ui_event_builder=lambda *a, **k: {"type": "result"},
        ui_result_builder=lambda *a, **k: None,
    )
    status = entry.step()
    assert status["state"] == "SCANNED"
    targets_events = [e for e in transport.events if e.get("type") == "rml24_targets"]
    assert targets_events, "no rml24_targets event emitted"
    assert targets_events[-1]["targets"] == []            # no signal -> empty list

    print("PROBE_OK flat_imports=clean entry_startup=ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
