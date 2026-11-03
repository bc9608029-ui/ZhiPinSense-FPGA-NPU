#!/usr/bin/env python3
"""Fail-closed control-contract tests without touching an SDR."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from standalone_control import Controller


class FakeLo:
    def __init__(self):
        self.current_hz = 2_400_000_000
        self.tunes = []

    def tune(self, hz):
        self.current_hz = int(hz)
        self.tunes.append(self.current_hz)
        return self.current_hz

    def flush(self):
        pass


def reject(ctl, command):
    try:
        ctl.validate(command)
    except ValueError:
        return
    raise AssertionError("command unexpectedly accepted: " + command)


ctl = Controller(2_400_000_000, 2_395_000_000, 2_405_000_000,
                 1_000_000, 2_300_000_000, 2_500_000_000, 101)
lo = FakeLo()

# AUTO_LOCK is deliberately not a user-facing third mode.
reject(ctl, "SET_MODE AUTO_LOCK")
reject(ctl, "SET_FIXED_HZ 2299999999")
reject(ctl, "SET_SCAN_RANGE_HZ 2405000000 2395000000 1000000")
reject(ctl, "SET_SCAN_RANGE_HZ 2300000000 2500000000 1")

c = ctl.submit("SET_FIXED_HZ 2401000000")
assert ctl.drain(lo) and c.done.is_set()
assert "applied_fixed_hz=2401000000" in c.response
assert ctl.snapshot()["fixed_hz"] == 2_401_000_000

c = ctl.submit("SET_SCAN_RANGE_HZ 2390000000 2410000000 1000000")
assert ctl.drain(lo) and c.done.is_set()
assert "scan_points=21" in c.response
s = ctl.snapshot()
assert (s["start_hz"], s["stop_hz"], s["step_hz"]) == (
    2_390_000_000, 2_410_000_000, 1_000_000)
print("test_standalone_control: PASS")
