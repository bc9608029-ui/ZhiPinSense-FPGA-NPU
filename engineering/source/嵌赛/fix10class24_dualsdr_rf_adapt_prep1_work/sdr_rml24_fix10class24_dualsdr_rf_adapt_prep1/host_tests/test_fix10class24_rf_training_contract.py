#!/usr/bin/env python3
"""test_fix10class24_rf_training_contract.py -- host tests for the training/compile contract.

Pure stdlib (no torch needed).  Verifies the preregistered training grid, the
checkpoint SHA gate, the F4 seed-statistics aggregator, and the go/no-go compile
gates.  Runs under ``python -I`` and under pytest.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "contracts"))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
import rml24_dualsdr_rf_dataset_v1 as C  # noqa: E402
import train_fix10class24_rf_adapt as T  # noqa: E402
import evaluate_fix10class24_rf_adapt as E  # noqa: E402
import rfadapt_compile_common as CC  # noqa: E402

SPEC = C.PILOT_TRAINING_SPEC


def test_training_spec_preregistered():
    assert SPEC["candidates"] == ["classification-head-only", "full-network-low-LR"]
    assert SPEC["learning_rates"] == [1e-5, 3e-5, 1e-4]
    assert SPEC["seeds"] == [17, 29, 43]
    assert SPEC["data_mix"] == ["real-rf-only", "clean-plus-real-rf-balanced"]
    assert SPEC["selection"] == "val-only-never-test"
    assert SPEC["weight_decay"] == 0.01
    assert SPEC["grad_clip_norm"] == 1.0
    assert SPEC["max_epochs"] == 20
    assert SPEC["early_stopping_patience"] == 4


def test_enumerate_runs_is_36():
    grid = list(T.enumerate_runs())
    assert len(grid) == 2 * 3 * 3 * 2  # candidate x lr x seed x data_mix
    assert len(grid) == 36


def test_enumerate_runs_values_in_spec():
    for r in T.enumerate_runs():
        assert r["candidate"] in SPEC["candidates"]
        assert r["lr"] in SPEC["learning_rates"]
        assert r["seed"] in SPEC["seeds"]
        assert r["data_mix"] in SPEC["data_mix"]


def test_validate_run_accepts_and_rejects():
    T.validate_run("classification-head-only", "real-rf-only", 17, 1e-5)  # ok
    try:
        T.validate_run("bogus", "real-rf-only", 17, 1e-5)
        assert False, "expected SystemExit"
    except SystemExit:
        pass
    try:
        T.validate_run("classification-head-only", "real-rf-only", 99, 1e-5)
        assert False, "expected SystemExit"
    except SystemExit:
        pass


def test_checkpoint_sha_gate_rejects_wrong_file():
    with tempfile.NamedTemporaryFile("wb", delete=False) as f:
        f.write(b"not the frozen checkpoint")
        p = f.name
    try:
        T.verify_checkpoint(p)
        assert False, "expected SystemExit"
    except SystemExit:
        pass
    finally:
        os.unlink(p)


def test_checkpoint_sha_gate_rejects_missing():
    try:
        T.verify_checkpoint("/nonexistent/best.pt")
        assert False, "expected SystemExit"
    except SystemExit:
        pass


def test_f4_seed_statistics():
    runs = [
        {"seed": 17, "best_val_accuracy": 0.80, "test_accuracy": 0.75},
        {"seed": 29, "best_val_accuracy": 0.84, "test_accuracy": 0.79},
        {"seed": 43, "best_val_accuracy": 0.82, "test_accuracy": 0.77},
    ]
    stats = E.compute_seed_statistics(runs)
    va = stats["best_val_accuracy"]
    assert va["min"] == 0.80 and va["max"] == 0.84
    assert abs(va["mean"] - 0.82) < 1e-9
    assert set(va["by_seed"].keys()) == {"17", "29", "43"}
    assert "std" in va and "test_accuracy" in stats


def _go_json(go, cand, base):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump({"go": go, "candidate_test_accuracy": cand,
               "baseline_test_accuracy": base}, f)
    f.close()
    return f.name


def test_compile_go_gate_rejects_no_go():
    p = _go_json(False, 0.85, 0.75)
    try:
        CC.check_go_gate(p)
        assert False, "expected SystemExit"
    except SystemExit:
        pass
    finally:
        os.unlink(p)


def test_compile_go_gate_rejects_candidate_not_beating():
    p = _go_json(True, 0.75, 0.75)
    try:
        CC.check_go_gate(p)
        assert False, "expected SystemExit"
    except SystemExit:
        pass
    finally:
        os.unlink(p)


def test_compile_go_gate_accepts_winning_candidate():
    p = _go_json(True, 0.85, 0.75)
    try:
        cand, base = CC.check_go_gate(p)
        assert cand == 0.85 and base == 0.75
    finally:
        os.unlink(p)


def test_train_enumerate_runs_without_torch():
    script = os.path.join(_ROOT, "scripts", "train_fix10class24_rf_adapt.py")
    r = subprocess.run([sys.executable, "-I", script, "--enumerate"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    grid = json.loads(r.stdout)
    assert grid["count"] == 36


def _run_all():
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    passed = failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS  {name}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"FAIL  {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed / {failed} failed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)
