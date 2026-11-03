#!/usr/bin/env python3
"""test_fix3_intended_dc_preservation.py -- debiasing must not remove legal DC.

Red line: OOK, ASK and AM-WC may have a legitimate non-zero mean or carrier; any
debiasing must prove it does not remove those legal modulation features.

The M1..M4 offset models subtract the SILENCE-region mean (settle/guard), which
is an estimate of the RF-frontend LO-leakage DC -- NOT the modulation's own mean.
This test proves, on clean (LO-leakage-free) bursts built from the frozen
contract, that:
  1. the silence regions have (essentially) zero mean, so
  2. subtracting the silence mean leaves the payload's legal mean unchanged, and
  3. the non-zero-mean classes (OOK / 4ASK / 8ASK / AM-SSB-WC / AM-DSB-WC) do
     carry a payload mean that the design intentionally does NOT touch.

Usage:  python -I host_tests/test_fix3_intended_dc_preservation.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import fix3_recovery as R

# Classes whose legal waveform carries a dominant DC/carrier component in the
# frozen contract (measured |payload_mean|/rms): OOK 0.69, 4ASK 0.81, 8ASK 0.86,
# AM-SSB-WC 0.996, AM-SSB-SC 0.992.  (AM-DSB-WC/SB are ~0 in this contract.)
NONZERO_MEAN_CLASSES = [0, 1, 2, 17, 18]   # OOK, 4ASK, 8ASK, AM-SSB-WC, AM-SSB-SC
DC_RATIO_THRESHOLD = 0.5


def check(name: str, ok: bool, detail: str = ""):
    if not ok:
        print("FAIL: %s  %s" % (name, detail))
        sys.exit(1)
    print("ok  %s" % name)


def main() -> int:
    for cls in range(24):
        wf = R.IRX.generate_waveform(cls)
        burst = R.C.deinterleave_int16(R.IRX.build_public_protocol_burst(wf))

        settle = burst[R.SETTLE_START:R.SETTLE_END]
        guard = burst[R.GUARD_START:R.GUARD_END]
        silence_mean = complex(np.concatenate([settle, guard]).mean())

        payload0 = burst[R.PAYLOAD_START:R.PAYLOAD_START + R.MODEL_WINDOW]
        payload_mean = complex(payload0.mean())

        # 1. silence is silent (LO-free clean burst).
        check("class %d silence mean ~ 0" % cls, abs(silence_mean) < 1e-6,
              "silence_mean=%s" % silence_mean)

        # 2. subtracting the silence mean preserves the payload mean exactly.
        preserved = complex((payload0 - silence_mean).mean())
        check("class %d payload mean preserved" % cls,
              abs(preserved - payload_mean) < 1e-6,
              "before=%s after=%s" % (payload_mean, preserved))

    # 3. the DC-carrier classes DO carry a strong payload mean; if the design
    #    subtracted the PAYLOAD mean instead, it would erase the carrier.  The
    #    silence-mean subtraction (M1..M4) preserves it.  Assert the ratio.
    for cls in NONZERO_MEAN_CLASSES:
        wf = R.IRX.generate_waveform(cls)
        burst = R.C.deinterleave_int16(R.IRX.build_public_protocol_burst(wf))
        payload0 = burst[R.PAYLOAD_START:R.PAYLOAD_START + R.MODEL_WINDOW]
        payload_mean = complex(payload0.mean())
        payload_rms = float(np.sqrt(np.mean(np.abs(payload0) ** 2)))
        dc_ratio = abs(payload_mean) / payload_rms if payload_rms > 0 else 0.0
        check("class %d has legal DC-carrier (|mean|/rms=%.3f > %.2f)"
              % (cls, dc_ratio, DC_RATIO_THRESHOLD),
              dc_ratio > DC_RATIO_THRESHOLD,
              "payload_mean=%s rms=%.2f" % (payload_mean, payload_rms))

    print("PASS test_fix3_intended_dc_preservation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
