#!/usr/bin/env python3
"""V2 data-source audit: verify the frozen signal/channel contract matches V1.

Fails closed if any frozen field diverges.  Prints the four data domains
(D1-D4) status and the frozen signal/channel contract digest for cross-checking
against ``BASELINE_SOURCE_SHA256.txt``.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from training.utils import load_yaml
from v2.contract import LABEL_ORDER_12, assert_12class_contract

FROZEN_SIGNAL = {
    "sample_rate": 128000.0,
    "symbol_rate": 16000.0,
    "samples_per_symbol": 8,
    "sample_length": 1024,
    "amplitude": 1.0,
}

FROZEN_OFDM = {"fft_length": 256, "cyclic_prefix": 64, "active_subcarriers": 48,
               "subcarrier_modulation": "QPSK"}

FROZEN_CHANNEL = {
    "awgn": {"enabled": True, "probability": 1.0, "snr_db": [-20.0, 20.0]},
    "cfo": {"enabled": True, "probability": 0.55, "hz": [-1200.0, 1200.0]},
    "multipath": {"enabled": True, "probability": 0.12, "num_taps": [2, 4], "max_delay": 10},
}

DATA_DOMAINS = {
    "D1": "synthetic_train", "D2": "synthetic_validation",
    "D3": "public_cross_domain (RadioML2018.01A)", "D4": "real_rf (empty in V1)",
}


def main() -> int:
    config = load_yaml("configs/v2_base.yaml")
    signal = config["signal"]
    assert_12class_contract(signal)

    failures: list[str] = []

    def require(cond: bool, message: str) -> None:
        if not cond:
            failures.append(message)
            print(f"FAIL  {message}")
        else:
            print(f"PASS  {message}")

    require(tuple(str(v).upper() for v in signal["modulations"]) == LABEL_ORDER_12,
            "label_order == frozen 12-class order")
    for key, expected in FROZEN_SIGNAL.items():
        require(float(signal.get(key, 0.0)) == float(expected), f"signal.{key} == {expected}")
    require(signal.get("ofdm", {}) == FROZEN_OFDM, f"signal.ofdm == {FROZEN_OFDM}")
    channel = config["channel"]
    for key, expected in FROZEN_CHANNEL.items():
        require(channel.get(key, {}) == expected, f"channel.{key} == {expected}")

    # Contract digest for cross-check against the baseline freeze manifest.
    canonical = {"signal": signal, "channel": channel,
                 "label_order": list(LABEL_ORDER_12)}
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    print(f"\ncontract_digest={digest}")

    print("\nData domains:")
    for domain, status in DATA_DOMAINS.items():
        print(f"  {domain}: {status}")

    if failures:
        print(f"\n{len(failures)} FAILURE(S)")
        return 1
    print("\nDATA AUDIT OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
