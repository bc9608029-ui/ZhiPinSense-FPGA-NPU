"""Sequential sweep: one bounded probe per step, no persistent target lock.

No transmitter metadata, classifier labels or reference payloads are used.
An off-centre detection is always recaptured at its estimated centre before DSP.
"""
from __future__ import annotations
import math
import time


class ContinuousSweep:
    def __init__(self):
        self.key = None
        self.index = 0
        self.cycle = 0

    def reset(self):
        self.key = None
        self.index = 0
        self.cycle = 0

    def probe(self, frequencies, lo, receive, detect, checkpoint,
              minimum_hz, maximum_hz, score_min=0.10,
              discovery_cfo_limit=1_152_000, centred_cfo_limit=1000, centred_detect=None):
        key = tuple(frequencies)
        if not key:
            raise ValueError('empty sweep')
        if self.key != key:
            self.key, self.index, self.cycle = key, 0, 0
        index, cycle = self.index, self.cycle
        self.index += 1
        if self.index == len(key):
            self.index = 0
            self.cycle += 1
        # Advance before any I/O: a failed detection/recovery never pins the sweep.
        checkpoint()
        actual = lo.tune(key[index])
        lo.flush()
        raw = receive()
        captured = time.time_ns()
        captured_monotonic = time.monotonic_ns()
        d = detect(raw)
        step = dict(scan_index=index + 1, scan_points=len(key), sweep_cycle=cycle,
                    lo_hz=actual, public_score=float(d.score),
                    cfo_hz=float(d.coarse_cfo_hz), captured_ns=captured,captured_monotonic_ns=captured_monotonic,
                    accepted=False)
        if not (math.isfinite(d.score) and math.isfinite(d.coarse_cfo_hz)
                and d.score >= score_min
                and abs(d.coarse_cfo_hz) <= discovery_cfo_limit):
            step['reason'] = 'DISCOVERY_REJECTED'
            return None, int(actual), captured, step
        centre = int(round(actual + d.coarse_cfo_hz))
        if not minimum_hz <= centre <= maximum_hz:
            step['reason'] = 'CENTRE_OUTSIDE_RANGE'
            return None, int(actual), captured, step
        checkpoint()
        actual = lo.tune(centre)
        lo.flush()
        raw = receive()
        captured = time.time_ns()
        captured_monotonic = time.monotonic_ns()
        confirm = (centred_detect or detect)(raw)
        step.update(centred_fallback_used=bool(getattr(confirm,'fallback_used',False)),primary_confirmed_score=float(getattr(confirm,'primary_score',confirm.score)),primary_confirmed_cfo_hz=float(getattr(confirm,'primary_cfo_hz',confirm.coarse_cfo_hz)))
        step.update(confirmed_lo_hz=actual, confirmed_ns=captured,confirmed_monotonic_ns=captured_monotonic,
                    confirmed_score=float(confirm.score),
                    confirmed_cfo_hz=float(confirm.coarse_cfo_hz))
        if not (math.isfinite(confirm.score) and math.isfinite(confirm.coarse_cfo_hz)
                and confirm.score >= score_min
                and abs(confirm.coarse_cfo_hz) <= centred_cfo_limit):
            step['reason'] = 'CENTRE_CONFIRMATION_FAILED'
            return None, int(actual), captured, step
        step.update(accepted=True, reason='CENTRED_PUBLIC_FRAME')
        return raw, int(round(actual + confirm.coarse_cfo_hz)), captured, step
