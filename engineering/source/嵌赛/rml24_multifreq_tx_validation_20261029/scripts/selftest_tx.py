#!/usr/bin/env python3
"""Offline counterexample suite for the multi-frequency TX source (NO SDR).

Part 1 exercises the REAL frozen functions (source SHA, path missing, shift
sign / frequency axis, dual peak over-limit, quantization saturation, resample
recovery).  Part 2 exercises the device control-flow (wrong URI, config
readback mismatch, buffer-before-restore ordering, stop/restore failure) against
a MOCK device -- clearly labelled SIMULATED, never presented as RF evidence.

Reproducible: run with ``--manifest`` / ``--dataset`` pointed at the frozen
sources; the mock-device tests need no hardware.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly, correlate

import tx_common as C
import multifreq_tx as M

_npass = 0
_nfail = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _npass, _nfail
    if cond:
        _npass += 1
        print(f"  PASS {name}")
    else:
        _nfail += 1
        print(f"  FAIL {name}  {detail}")


def raises(fn, *a, **kw):
    try:
        fn(*a, **kw)
        return None
    except (SystemExit, ValueError, AssertionError, FileNotFoundError, OSError) as e:
        return type(e).__name__


def _payload(i_vals, q_vals) -> bytes:
    vals = np.zeros(2048, dtype="<f4")
    vals[0:1024] = i_vals
    vals[1024:2048] = q_vals
    return vals.tobytes()


def _recover(z: np.ndarray, df: float) -> np.ndarray:
    n = np.arange(len(z))
    base = z * np.exp(-2j * np.pi * df * n / C.TX_SAMPLE_RATE)
    return resample_poly(base, 1, C.UPSAMPLE)


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    cc = correlate(a, b, mode="full", method="fft")
    lag = int(np.argmax(np.abs(cc))) - (b.size - 1)
    x = a[lag:lag + b.size] if lag >= 0 else a[:lag]
    y = b if lag >= 0 else b[-lag:]
    n = min(x.size, y.size)
    x, y = x[:n], y[:n]
    d = np.sqrt(np.sum(np.abs(x) ** 2) * np.sum(np.abs(y) ** 2))
    return 0.0 if d == 0 else float(abs(np.vdot(x, y)) / d)


# ---------------------------------------------------------------------------
# Part 1: real frozen functions
# ---------------------------------------------------------------------------

def test_shift_sign_and_freq_axis():
    frame = C.build_frame(_payload(np.linspace(-0.5, 0.5, 1024), np.linspace(0.5, -0.5, 1024)))
    shifted = C.resample_shift(frame, -1.8e6)  # A path, down shift
    c_correct = _corr(_recover(shifted, -1.8e6), frame)
    c_wrong = _corr(_recover(shifted, +1.8e6), frame)
    check("shift_sign_correct_recovers", c_correct >= 0.99, f"corr={c_correct}")
    check("shift_sign_wrong_sign_rejected", c_wrong < 0.5, f"corr={c_wrong}")


def test_dual_peak_over_limit():
    # source = 40+40j -> scaled peak 40*SCALE > 2047 -> clip guard must raise
    frame = _payload(np.full(1024, 40.0, dtype="<f4"), np.full(1024, 40.0, dtype="<f4"))
    check("dual_peak_over_limit_clip_guard", raises(C.build_frame, frame) == "ValueError")


def test_quantization_saturation():
    # over-range float signal MUST be flagged (proves the check is not vacuous)
    over = np.full(100, 3000.0 + 0j)
    check("overrange_detected", C.saturation_count(over) > 0)
    # a normal frame is clean
    frame = C.build_frame(_payload(np.linspace(-0.5, 0.5, 1024), np.zeros(1024, dtype="<f4")))
    z = C.resample_shift(frame, -1.8e6) + C.resample_shift(frame, +1.8e6)
    check("normal_frame_no_saturation", C.saturation_count(z) == 0)


def test_source_sha_error(args):
    rows = C.load_manifest(Path(args.manifest))
    r3 = next(v for v in rows if int(v["file"].split("_")[0]) == args.class_a)
    r9 = next(v for v in rows if int(v["file"].split("_")[0]) == args.class_b)
    bad = dict(r3)
    bad["source_sha256"] = "0" * 64
    with tempfile.TemporaryDirectory() as td:
        mf = Path(td) / "bad_manifest.json"
        mf.write_text(json.dumps({"records": [bad, r9]}))
        ns = argparse.Namespace(manifest=str(mf), dataset=args.dataset,
                                class_a=args.class_a, class_b=args.class_b)
        check("source_sha_error_detected", raises(M.build_scenarios, ns) == "SystemExit")


def test_path_missing(args):
    rows = C.load_manifest(Path(args.manifest))
    r3 = next(v for v in rows if int(v["file"].split("_")[0]) == args.class_a)
    r9 = next(v for v in rows if int(v["file"].split("_")[0]) == args.class_b)
    ghost = dict(r3)
    ghost["file"] = f"{args.class_a:02d}_99.bin"  # same class prefix, nonexistent instance
    with tempfile.TemporaryDirectory() as td:
        mf = Path(td) / "ghost_manifest.json"
        mf.write_text(json.dumps({"records": [ghost, r9]}))
        ns = argparse.Namespace(manifest=str(mf), dataset=args.dataset,
                                class_a=args.class_a, class_b=args.class_b)
        r = raises(M.build_scenarios, ns)
        check("path_missing_detected", r in ("FileNotFoundError", "OSError"), f"raised={r}")


def test_resample_recovery(args):
    rows = C.load_manifest(Path(args.manifest))
    sel = next(v for v in rows if int(v["file"].split("_")[0]) == args.class_a)
    data = (Path(args.dataset) / sel["file"]).read_bytes()
    frame = C.build_frame(data)
    shifted = C.resample_shift(frame, -1.8e6)
    rec = _recover(shifted, -1.8e6)
    check("resample_recovery_corr", _corr(rec, frame) >= 0.99, f"corr={_corr(rec, frame)}")


# ---------------------------------------------------------------------------
# Part 2: mock device (SIMULATED -- not RF evidence)
# ---------------------------------------------------------------------------

class FakeRadio:
    def __init__(self, ignore_set=False, fail_stop=False, close_errors=None, fail_close=False):
        self.ignore_set = ignore_set
        self.fail_stop = fail_stop
        self.close_errors = list(close_errors or [])
        self.fail_close = fail_close
        self.tx, self.tlo = "tx", "tlo"
        self.attrs = {
            ("tx", "hardwaregain"): "-60.000000 dB",
            ("tx", "sampling_frequency"): "10240000.000000",
            ("tx", "rf_bandwidth"): "18000000.000000",
            ("tlo", "frequency"): "2401800000.000000",
            ("tlo", "powerdown"): "1",
        }
        self.saved, self.buffers, self.order = [], [], []

    def get(self, ch, key):
        return self.attrs[(ch, key)]

    def set(self, ch, key, value):
        self.saved.append((ch, key, self.attrs[(ch, key)]))
        if not self.ignore_set:
            self.attrs[(ch, key)] = str(value)

    def send(self, z):
        b = object()
        self.buffers.append(b)
        return b

    def stop(self, b):
        self.order.append("stop")
        if self.fail_stop:
            raise RuntimeError("stop failed")
        if b in self.buffers:
            self.buffers.remove(b)

    def close(self):
        self.order.append("close")
        if self.fail_close:
            raise RuntimeError("close failed")
        for ch, key, value in self.saved[::-1]:
            self.attrs[(ch, key)] = value
        self.buffers = []
        return list(self.close_errors)


def test_wrong_uri():
    r = raises(M.verify_tx_uri, ["usb:1.12.5"], "usb:9.9.9")
    check("wrong_uri_rejected", r == "SystemExit", f"raised={r}")
    check("correct_uri_accepted", M.verify_tx_uri(["usb:1.12.5"], "usb:1.12.5") is True)


def test_config_readback_mismatch():
    rb, ok = M.apply_config_and_readback(FakeRadio(ignore_set=True))
    check("config_readback_mismatch_detected", ok is False, json.dumps(rb))
    rb2, ok2 = M.apply_config_and_readback(FakeRadio())
    check("config_readback_match_ok", ok2 is True, json.dumps(rb2))


def test_buffer_before_restore():
    radio = FakeRadio()
    buffer = radio.send(np.zeros(16))
    errs = M.destroy_buffer_then_restore(radio, buffer)
    check("buffer_destroyed_before_restore", radio.order == ["stop", "close"], str(radio.order))
    check("clean_restore_no_errors", errs == [], str(errs))


def test_stop_restore_failure():
    r1 = FakeRadio(fail_stop=True)
    b1 = r1.send(np.zeros(16))
    errs1 = M.destroy_buffer_then_restore(r1, b1)
    check("stop_failure_recorded", any(e[0] == "stop" for e in errs1), str(errs1))

    r2 = FakeRadio(close_errors=[("restore_attr", -1)])
    b2 = r2.send(np.zeros(16))
    errs2 = M.destroy_buffer_then_restore(r2, b2)
    check("restore_failure_recorded", errs2 == [("restore_attr", -1)], str(errs2))

    r3 = FakeRadio(fail_close=True)
    b3 = r3.send(np.zeros(16))
    errs3 = M.destroy_buffer_then_restore(r3, b3)
    check("close_failure_recorded", any(e[0] == "close" for e in errs3), str(errs3))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="F:/嵌赛/rml24_final_integration1_work/pc_runtime/selftest_manifest_240.json")
    ap.add_argument("--dataset", default="F:/嵌赛/rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/dataset")
    ap.add_argument("--class-a", type=int, default=3)
    ap.add_argument("--class-b", type=int, default=9)
    args = ap.parse_args()

    print("== Part 1: real frozen functions ==")
    test_shift_sign_and_freq_axis()
    test_dual_peak_over_limit()
    test_quantization_saturation()
    test_source_sha_error(args)
    test_path_missing(args)
    test_resample_recovery(args)

    print("== Part 2: mock device (SIMULATED) ==")
    test_wrong_uri()
    test_config_readback_mismatch()
    test_buffer_before_restore()
    test_stop_restore_failure()

    print(f"\nRESULT pass={_npass} fail={_nfail}")
    return 1 if _nfail else 0


if __name__ == "__main__":
    raise SystemExit(main())
