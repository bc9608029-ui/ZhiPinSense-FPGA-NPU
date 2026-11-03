"""Regression tests for the two-phase final-evaluation protocol fix (task 39e5).

Calibration (``run_ood_baselines``) is validation-only; the final evaluation reads
the frozen threshold manifest and touches ``test`` / ``ood_final_test`` exactly
once each, guarded by a one-time access ledger.  All tests are offline — no HDF5,
no model, no checkpoint — via monkeypatching.
"""

from __future__ import annotations

import json
import inspect

import numpy as np
import pytest


def _frozen_thresholds() -> dict:
    return {
        "conservative": {"threshold": 0.1, "id_frr": 0.04, "ood_far": 0.8},
        "balanced": {"threshold": 0.5, "id_frr": 0.02, "ood_far": 0.1},
        "strict": {"threshold": 0.9, "id_frr": 0.01, "ood_far": 0.03},
    }


def _valid_threshold_manifest() -> dict:
    return {
        "model_sha256": "a" * 64,
        "checkpoint_sha256": "b" * 64,
        "score_method": "energy",
        "direction": "higher_is_ood",
        "temperature": 1.0,
        "thresholds": _frozen_thresholds(),
        "calibration_dataset_sha256": "c" * 64,
        "calibration_split_sha256": "d" * 64,
        "target_operating_point": "balanced",
        "calibration_samples": {"id": 64, "ood": 1280},
        "creation_seed": 2026,
    }


def _final_manifest() -> dict:
    return {
        "checkpoint_path": "unused.pt",
        "checkpoint_sha256": "b" * 64,
        "label_contract_sha256": "a" * 64,
        "dataset_sha256": "c" * 64,
    }


def _fake_id(n: int = 64, c: int = 24) -> tuple[np.ndarray, np.ndarray]:
    """Well-separated ID logits with all-correct predictions."""
    logits = np.full((n, c), -5.0, dtype=np.float64)
    labels = np.arange(n) % c
    logits[np.arange(n), labels] = 5.0
    return logits, labels.astype(np.int64)


class _Rec:
    def __init__(self, planar: np.ndarray) -> None:
        self.planar = planar


def _fake_records() -> _Rec:
    return _Rec(np.zeros((16, 2, 1024), dtype=np.float32))


def _record_splits(monkeypatch, module, splits: list) -> None:
    monkeypatch.setattr(module, "generate_ood_records",
                        lambda family, split, **kw: splits.append(split) or _fake_records())


def _fake_ood_logits() -> np.ndarray:
    return np.random.default_rng(7).normal(size=(16, 24)).astype(np.float32)


def test_calibration_id_split_defaults_to_validation_and_never_touches_test(monkeypatch):
    from evaluation import evaluate_ood as eo

    # Defect 1: the calibration entry point must default to ID validation, not test.
    sig = inspect.signature(eo.evaluate_ood_rml24)
    assert sig.parameters["id_split"].default == "validation"

    splits: list[str] = []
    _record_splits(monkeypatch, eo, splits)
    monkeypatch.setattr(eo, "run_model_logits",
                        lambda m, p, d, bs: np.zeros((p.shape[0], 24), dtype=np.float32))
    id_logits, id_labels = _fake_id()
    eo.calibrate_ood_thresholds(
        None, None, id_logits, id_labels,
        signal_config={}, ood_seed=3407, count_per_modulation=256, threshold_family="far",
    )
    assert splits and all(s == "ood_validation" for s in splits)
    assert "test" not in splits


def test_calibration_never_constructs_ood_final_test(monkeypatch):
    from evaluation import evaluate_ood as eo

    splits: list[str] = []
    _record_splits(monkeypatch, eo, splits)
    monkeypatch.setattr(eo, "run_model_logits",
                        lambda m, p, d, bs: np.zeros((p.shape[0], 24), dtype=np.float32))
    id_logits, id_labels = _fake_id()
    eo.calibrate_ood_thresholds(
        None, None, id_logits, id_labels,
        signal_config={}, ood_seed=3407, count_per_modulation=256, threshold_family="far",
    )
    assert "ood_final_test" not in splits


def test_final_fails_closed_when_threshold_manifest_missing(monkeypatch, tmp_path):
    from scripts import run_final_evaluation as rfe

    monkeypatch.setattr(rfe, "load_yaml", lambda p: {"seed": 2026})
    monkeypatch.setattr(rfe, "resolve_checkpoint", lambda p: "unused.pt")

    final_path = tmp_path / "final_checkpoint_manifest.json"
    final_path.write_text(json.dumps(_final_manifest()), encoding="utf-8")
    missing = tmp_path / "nope.json"
    with pytest.raises(FileNotFoundError):
        rfe.run_final_evaluation(
            "cfg", str(final_path), str(missing),
            output=str(tmp_path / "out.json"), gate_path=str(tmp_path / "gate.json"), run_id="t",
        )
    assert not (tmp_path / "gate.json").exists()  # gate never acquired


def test_checkpoint_sha_mismatch_fails_closed():
    from scripts.run_final_evaluation import verify_final_identity

    final = _final_manifest()
    verify_final_identity(final, _valid_threshold_manifest())  # matching -> ok

    bad_checkpoint = _valid_threshold_manifest()
    bad_checkpoint["checkpoint_sha256"] = "e" * 64
    with pytest.raises(RuntimeError):
        verify_final_identity(final, bad_checkpoint)

    bad_label = _valid_threshold_manifest()
    bad_label["model_sha256"] = "e" * 64
    with pytest.raises(RuntimeError):
        verify_final_identity(final, bad_label)

    bad_dataset = _valid_threshold_manifest()
    bad_dataset["calibration_dataset_sha256"] = "e" * 64
    with pytest.raises(RuntimeError):
        verify_final_identity(final, bad_dataset)


def test_final_scoring_never_calls_calibrate_temperature(monkeypatch):
    from evaluation import evaluate_ood as eo

    def boom(*a, **k):
        raise AssertionError("calibrate_temperature must not be called in final scoring")
    monkeypatch.setattr(eo, "calibrate_temperature", boom)
    monkeypatch.setattr(eo, "generate_ood_records",
                        lambda family, split, **kw: _fake_records())
    monkeypatch.setattr(eo, "run_model_logits", lambda m, p, d, bs: _fake_ood_logits())

    id_logits, id_labels = _fake_id()
    report = eo.score_ood_final(
        None, None, id_logits, id_labels,
        score_method="energy", temperature=1.0, thresholds=_frozen_thresholds(),
        signal_config={}, ood_seed=3407, count_per_modulation=256,
        families=["far"], n_boot=50,
    )
    assert report["score_method"] == "energy"


def test_final_scoring_never_calls_select_thresholds(monkeypatch):
    from evaluation import evaluate_ood as eo

    def boom(*a, **k):
        raise AssertionError("select_thresholds must not be called in final scoring")
    monkeypatch.setattr(eo, "select_thresholds", boom)
    monkeypatch.setattr(eo, "generate_ood_records",
                        lambda family, split, **kw: _fake_records())
    monkeypatch.setattr(eo, "run_model_logits", lambda m, p, d, bs: _fake_ood_logits())

    id_logits, id_labels = _fake_id()
    report = eo.score_ood_final(
        None, None, id_logits, id_labels,
        score_method="energy", temperature=1.0, thresholds=_frozen_thresholds(),
        signal_config={}, ood_seed=3407, count_per_modulation=256,
        families=["far"], n_boot=50,
    )
    assert report["families"]["energy"]["thresholds"] == _frozen_thresholds()


def test_id_test_inferred_exactly_once(monkeypatch, tmp_path):
    from scripts import run_final_evaluation as rfe

    id_calls: list[str] = []
    def fake_eval(config, ckpt, split="validation", **kw):
        id_calls.append(split)
        logits, labels = _fake_id(32)
        return {
            "metrics": {"accuracy": 0.9},
            "samples": 32,
            "split": split,
            "numeric_mode": "fp32",
            "logits": logits.astype(np.float32),
            "labels": labels,
        }

    captured: dict = {}
    def fake_final(config, ckpt, tmanifest, *, id_result, **kw):
        captured["result"] = id_result
        return {"families": {"energy": {"families": {"far": {"ranking": {"auroc": 0.95}}}}}}

    monkeypatch.setattr(rfe, "load_yaml", lambda p: {"seed": 2026})
    monkeypatch.setattr(rfe, "resolve_checkpoint", lambda p: "unused.pt")
    monkeypatch.setattr(rfe, "read_threshold_manifest", lambda p: _valid_threshold_manifest())
    monkeypatch.setattr(rfe, "evaluate_rml24", fake_eval)
    monkeypatch.setattr(rfe, "evaluate_ood_final_rml24", fake_final)
    monkeypatch.setattr(rfe, "fake_int8_report_rml24", lambda c, cp: {"accuracy_drop": 0.0})
    monkeypatch.setattr(rfe, "evaluate_rml24_channel_ood", lambda c, cp: {"domains": {}})
    monkeypatch.setattr(rfe, "save_json", lambda data, path: None)
    monkeypatch.setattr(rfe, "_write_recommendation_md", lambda *a, **k: None)

    final_path = tmp_path / "final_checkpoint_manifest.json"
    final_path.write_text(json.dumps(_final_manifest()), encoding="utf-8")
    threshold_path = tmp_path / "ood_threshold_manifest.json"
    threshold_path.write_text(json.dumps(_valid_threshold_manifest()), encoding="utf-8")
    gate = tmp_path / "final_test_access.json"

    report = rfe.run_final_evaluation(
        "cfg", str(final_path), str(threshold_path),
        output=str(tmp_path / "out.json"), gate_path=str(gate), run_id="test-run",
    )

    assert id_calls == ["test"]  # exactly one ID test inference
    assert captured["result"]["split"] == "test"  # and it was reused verbatim
    ledger = json.loads(gate.read_text(encoding="utf-8"))
    assert ledger["status"] == "COMPLETE"
    assert ledger["id_test_accessed"] is True
    assert ledger["ood_final_test_accessed"] is True
    assert ledger["run_id"] == "test-run"


def test_ood_final_test_scored_exactly_once_per_family(monkeypatch):
    from evaluation import evaluate_ood as eo

    splits: list[str] = []
    _record_splits(monkeypatch, eo, splits)
    monkeypatch.setattr(eo, "run_model_logits", lambda m, p, d, bs: _fake_ood_logits())

    id_logits, id_labels = _fake_id()
    eo.score_ood_final(
        None, None, id_logits, id_labels,
        score_method="energy", temperature=1.0, thresholds=_frozen_thresholds(),
        signal_config={}, ood_seed=3407, count_per_modulation=256,
        families=["near_24", "far"], n_boot=50,
    )
    assert splits == ["ood_final_test", "ood_final_test"]
    assert all(s == "ood_final_test" for s in splits)


def test_second_final_evaluation_rejected(tmp_path):
    from evaluation.final_test_gate import acquire_gate, complete_gate

    gate = tmp_path / "final_test_access.json"
    acquire_gate(gate, run_id="r1", checkpoint_sha256="b" * 64,
                 threshold_manifest_sha256="e" * 64, dataset_sha256="c" * 64)
    with pytest.raises(RuntimeError):  # STARTED already claimed
        acquire_gate(gate, run_id="r2", checkpoint_sha256="b" * 64,
                     threshold_manifest_sha256="e" * 64, dataset_sha256="c" * 64)
    complete_gate(gate)
    with pytest.raises(RuntimeError):  # COMPLETE still blocks
        acquire_gate(gate, run_id="r3", checkpoint_sha256="b" * 64,
                     threshold_manifest_sha256="e" * 64, dataset_sha256="c" * 64)


def test_final_decision_uses_frozen_threshold(monkeypatch):
    from evaluation import evaluate_ood as eo

    monkeypatch.setattr(eo, "generate_ood_records",
                        lambda family, split, **kw: _fake_records())
    monkeypatch.setattr(eo, "run_model_logits", lambda m, p, d, bs: _fake_ood_logits())

    id_logits, id_labels = _fake_id()
    thresholds = _frozen_thresholds()
    report = eo.score_ood_final(
        None, None, id_logits, id_labels,
        score_method="energy", temperature=1.0, thresholds=thresholds,
        signal_config={}, ood_seed=3407, count_per_modulation=256,
        families=["far"], n_boot=50,
    )
    # The frozen thresholds are echoed verbatim (never re-selected) ...
    assert report["families"]["energy"]["thresholds"] == thresholds
    far = report["families"]["energy"]["families"]["far"]
    assert far["working_points"]["balanced"]["threshold"] == 0.5
    # ... and the UNKNOWN decision uses the frozen value, not a re-fit one.
    ood_scores = np.asarray(far["ood_scores"], dtype=np.float64)
    decisions = np.asarray(far["decisions"]["balanced"], dtype=bool)
    assert bool(np.array_equal(decisions, ood_scores > 0.5))


def test_resolve_checkpoint_does_not_modify_checkpoint_bytes(tmp_path):
    from scripts._resolve_checkpoint import _sha256, resolve_checkpoint

    ckpt = tmp_path / "best.pt"
    content = b"fake-checkpoint-bytes\x00\x01\x02\x03"
    ckpt.write_bytes(content)
    sha = _sha256(ckpt)

    manifest = tmp_path / "final_checkpoint_manifest.json"
    manifest.write_text(
        json.dumps({"checkpoint_path": str(ckpt), "checkpoint_sha256": sha}),
        encoding="utf-8",
    )
    assert resolve_checkpoint(str(manifest)) == str(ckpt)
    assert ckpt.read_bytes() == content  # bytes unchanged
    assert _sha256(ckpt) == sha          # SHA unchanged
