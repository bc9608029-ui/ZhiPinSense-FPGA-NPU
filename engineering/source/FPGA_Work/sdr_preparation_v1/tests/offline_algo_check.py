#!/usr/bin/env python3
# Offline reference check of the sdr_adapter pure-logic algorithms.
#
# The production code is C++ (sdr_adapter/*.hpp, tested by test_all.cpp on the
# board toolchain).  This file is a byte-for-byte-LOGIC port of the two most
# error-prone pieces -- the frame-sequence monitor and the perf-stats summary --
# so the algorithms can be executed and verified on a host with no C++ toolchain.
# It runs the SAME cases that test_all.cpp encodes.

import math
import sys

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL {name}")


# ---- SequenceMonitor (mirror of sequence_monitor.hpp) -----------------------

class SequenceStats:
    def __init__(self):
        self.total = 0
        self.overflow = 0
        self.dropped = 0
        self.duplicate = 0
        self.reorder = 0
        self.discontinuity = 0
        self.gap = 0
        self.short_frame = 0
        self.last_frame_id = -1
        self.seen = False


class SequenceMonitor:
    def __init__(self):
        self.s = SequenceStats()

    def observe(self, frame_id, overflow=False, dropped=False,
                discontinuity=False, short_frame=False):
        s = self.s
        s.total += 1
        if overflow: s.overflow += 1
        if dropped: s.dropped += 1
        if discontinuity: s.discontinuity += 1
        if short_frame: s.short_frame += 1

        if not s.seen:
            s.seen = True
            s.last_frame_id = frame_id
            return
        if frame_id == s.last_frame_id:
            s.duplicate += 1
        elif frame_id < s.last_frame_id:
            s.reorder += 1
        else:
            jump = frame_id - s.last_frame_id - 1
            if jump > 0:
                s.gap += jump
                s.dropped += jump
            s.last_frame_id = frame_id

    def healthy(self):
        s = self.s
        return (s.duplicate == 0 and s.reorder == 0 and s.gap == 0 and
                s.overflow == 0 and s.dropped == 0 and s.discontinuity == 0 and
                s.short_frame == 0)

    def reset(self):
        self.s = SequenceStats()


def test_sequence_monitor():
    # clean stream
    m = SequenceMonitor()
    for i in range(10):
        m.observe(i)
    check("seq clean healthy", m.healthy())
    check("seq clean total", m.s.total == 10)
    check("seq clean no anomalies", m.s.duplicate == 0 and m.s.reorder == 0
          and m.s.gap == 0 and m.s.dropped == 0)

    # gap
    m = SequenceMonitor()
    m.observe(0); m.observe(2)
    check("seq gap not healthy", not m.healthy())
    check("seq gap count", m.s.gap == 1 and m.s.dropped == 1)

    # duplicate
    m = SequenceMonitor()
    m.observe(0); m.observe(1); m.observe(1)
    check("seq duplicate", m.s.duplicate == 1 and m.s.reorder == 0)

    # reorder
    m = SequenceMonitor()
    m.observe(0); m.observe(1); m.observe(0)
    check("seq reorder", m.s.reorder == 1 and m.s.duplicate == 0)

    # producer flags
    m = SequenceMonitor()
    m.observe(0, overflow=True)
    m.observe(1, dropped=True)
    m.observe(2, discontinuity=True)
    m.observe(3, short_frame=True)
    check("seq flags", m.s.overflow == 1 and m.s.dropped == 1 and
          m.s.discontinuity == 1 and m.s.short_frame == 1 and not m.healthy())

    # reset
    m = SequenceMonitor()
    m.observe(0); m.observe(2)
    m.reset()
    check("seq reset", m.healthy() and m.s.total == 0)


# ---- PerfStats (mirror of perf_stats.hpp) -----------------------------------

class PerfStats:
    def __init__(self):
        self.m = {}

    def record(self, stage, us):
        s = self.m.setdefault(stage, [0, 0.0, None, None])  # count,total,min,max
        s[0] += 1
        s[1] += us
        s[2] = us if s[2] is None else min(s[2], us)
        s[3] = us if s[3] is None else max(s[3], us)

    def count(self, stage):
        return self.m.get(stage, [0])[0]

    def avg_us(self, stage):
        s = self.m.get(stage)
        if s is None or s[0] == 0:
            return 0.0
        return s[1] / s[0]

    def summary(self):
        order = ["sdr_capture", "resample_frame", "plddr_transfer",
                 "fpga_process", "npu_infer", "end_to_end"]
        parts = []
        for k in order:
            if k not in self.m:
                continue
            c, t, mn, mx = self.m[k]
            parts.append(f"{k} cnt={c} avg_us={t/c if c else 0:.3f} "
                         f"min_us={mn:.3f} max_us={mx:.3f}")
        return " ".join(parts)


def test_perf_stats():
    p = PerfStats()
    p.record("npu_infer", 10.0)
    p.record("npu_infer", 20.0)
    p.record("npu_infer", 30.0)
    check("perf count", p.count("npu_infer") == 3)
    check("perf avg", abs(p.avg_us("npu_infer") - 20.0) < 1e-9)
    check("perf unknown count", p.count("fpga_process") == 0)
    s = p.summary()
    check("perf summary contains stage", "npu_infer" in s and "cnt=3" in s)


def main():
    test_sequence_monitor()
    test_perf_stats()
    print(f"\nOFFLINE_ALGO_CHECK pass={PASS} fail={FAIL}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
