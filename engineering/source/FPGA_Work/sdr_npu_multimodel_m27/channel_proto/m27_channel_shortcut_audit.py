"""M27 channel prototype generator-shortcut audit (spec §十一).

Detects whether the label could be recovered by a shortcut rather than genuine signal
structure: (a) a fixed/magic per-label power, (b) a deterministic mean-power encoding,
or (c) a format/metadata leak.  If any shortcut is found, prints
``CHANNEL_IMPAIRMENT_PROTOCOL_INVALID reason=generator_shortcut`` and exits non-zero.
"""

from __future__ import annotations

import sys

import numpy as np


def audit_shortcuts(splits, tol=0.05):
    """Returns (ok, reasons).  Checks every split."""
    reasons = []
    for name, (x, y, _snr) in splits.items():
        n_labels = int(y.max()) + 1
        mean_power = np.zeros(n_labels)
        for lab in range(n_labels):
            xl = x[y == lab]
            # per-element power of a unit-RMS complex signal is ~0.5 for every label
            mean_power[lab] = float(np.mean(xl ** 2))

        # (a)+(b): the label must not be a (monotone) function of power -> all labels
        # share ~the same mean power.
        if np.ptp(mean_power) > tol:
            reasons.append(f"{name}: mean power varies across labels "
                           f"(ptp {np.ptp(mean_power):.4f})")
        # (c): format leak — dtype must be plain float32 with no extra channel.
        if x.dtype != np.float32 or x.shape[1] != 2 or x.shape[2] != 1024:
            reasons.append(f"{name}: format leak (dtype/shape={x.dtype}/{x.shape})")

        # a label must not correlate with mean power (undefined corr = constant
        # power = fine, so only flag a *finite* strong correlation)
        with np.errstate(invalid="ignore", divide="ignore"):
            corr = np.corrcoef(np.arange(n_labels), mean_power)[0, 1]
        if np.isfinite(corr) and abs(corr) > 0.3:
            reasons.append(f"{name}: label correlates with mean power (r={corr:.3f})")

    ok = len(reasons) == 0
    if not ok:
        print("CHANNEL_IMPAIRMENT_PROTOCOL_INVALID reason=generator_shortcut")
        for r in reasons:
            print(f"  - {r}")
    return ok, reasons


def main():
    from m27_channel_generator import generate_all
    splits = generate_all(seed=2026, samples_per_label=32)
    ok, reasons = audit_shortcuts(splits)
    if not ok:
        sys.exit(1)
    print("CHANNEL_IMPAIRMENT_PROTOCOL_OK (no generator shortcut)")
    sys.exit(0)


if __name__ == "__main__":
    main()
