#!/usr/bin/env python3
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))
from feature_contract import exact_features


def check(name, iq, expected_energy=None, expected_peak=None):
    out = exact_features(iq)
    assert out["sample_count"] == len(iq)
    assert np.array_equal(out["power"], iq[:, 0].astype(np.int64) ** 2 + iq[:, 1].astype(np.int64) ** 2)
    if len(iq):
        assert out["lag_re"][0] == 0 and out["lag_im"][0] == 0
    if expected_energy is not None:
        assert out["energy"] == expected_energy
    if expected_peak is not None:
        assert out["peak_power"] == expected_peak
    return name


def main():
    rng = np.random.default_rng(20261027)
    cases = []
    cases.append(check("zeros", np.zeros((1024, 2), np.int16), 0, 0))
    impulse = np.zeros((1024, 2), np.int16); impulse[0] = (-32768, -32768)
    cases.append(check("fullscale_impulse", impulse, 2**31, 2**31))
    extrema = np.array([[32767, 32767], [-32768, 32767], [0, -32768]], np.int16)
    cases.append(check("extrema", extrema))
    random_iq = rng.integers(-32768, 32768, size=(1024, 2), dtype=np.int16)
    cases.append(check("random1024", random_iq))
    a = exact_features(random_iq)
    b = exact_features(random_iq.copy())
    assert a["energy"] == b["energy"] and np.array_equal(a["lag_im"], b["lag_im"])
    print(json.dumps({"result":"PASS", "checks":len(cases)+1, "cases":cases}, ensure_ascii=False))


if __name__ == "__main__":
    main()
