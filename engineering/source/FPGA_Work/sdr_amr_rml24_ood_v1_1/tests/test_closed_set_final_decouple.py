"""Regression tests for the closed-set final evaluation decoupling.

``--closed-set-only`` runs the 24-class closed-set ``test`` exactly once and never
touches any OOD quantity (no ``ood_final_test``, no OOD threshold manifest, no OOD
final ledger).  The ID ``test`` access is guarded by its own one-time ledger, fully
independent of the OOD final ledger.  All tests are offline — no HDF5, no model, no
checkpoint — via monkeypatching.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from contracts.rml24_contract import LABEL_ORDER_24
from v2.candidate_signature import label_contract_sha256


def _final_manifest() -> dict:
    return {
        "candidate_signature": "a" * 64,
        "selected_seed": 2027,
        "checkpoint_path": "unused.pt",
        "checkpoint_sha256": "b" * 64,
        "model_name": "RML2018_24_BENCHMARK",
        "class_count": 24,
        "label_contract_sha256": label_contract_sha256(),
        "config_sha256": "d" * 64,
        "dataset_sha256": "c" * 64,
        "selection_metric": "rated_0_20_accuracy",
        "selection_value": 0.89,
    }


def _fake_id_result(n: int = 240, c: int = 24) -> dict:
    rng = np.random.default_rng(2026)
    logits = rng.normal(size=(n, c)).astype(np.float32)
    labels = rng.integers(0, c, size=n).astype(np.int64)
    preds = logits.argmax(1)
    cm = np.zeros((c, c), dtype=np.int64)
    np.add.at(cm, (labels, preds), 1)
    per_class = [float(cm[i, i] / cm[i].sum()) if cm[i].sum() else 0.0 for i in range(c)]
    acc = float((preds == labels).mean())
    return {
        "metrics": {
            "accuracy": acc,
            "macro_f1": acc,
            "rated_0_20_accuracy": acc,
            "high_10_20_accuracy": acc,
            "snr_0_accuracy": acc,
            "min_per_class_accuracy": min(per_class),
            "per_class_accuracy": per_class,
            "per_snr_accuracy": {"0": acc, "10": acc},
            "selection_score": acc,
        },
        "logits": logits,
        "labels": labels,
        "samples": n,
        "split": "test",
        "checkpoint_epoch": 80,
        "numeric_mode": "fp32",
        "final_blind_test_accessed": True,
    }


def _run(monkeypatch, rfe, tmp_path, *, gate="gate.json", run_id="t") -> dict:
    manifest = _final_manifest()
    mp = tmp_path / "final_checkpoint_manifest.json"
    mp.write_text(json.dumps(manifest), encoding="utf-8")
    return rfe.run_closed_set_final_evaluation(
        "cfg", str(mp),
        output=str(tmp_path / "out.json"),
        report_md=str(tmp_path / "report.md"),
        gate_path=str(tmp_path / gate),
        run_id=run_id,
    )


def _patch_pure(monkeypatch, rfe) -> None:
    monkeypatch.setattr(rfe, "load_yaml", lambda p: {"seed": 2026})
    monkeypatch.setattr(rfe, "resolve_checkpoint", lambda p: "unused.pt")
    monkeypatch.setattr(rfe, "evaluate_rml24",
                        lambda c, cp, split="validation", **kw: _fake_id_result())


def test_closed_set_only_calls_evaluate_rml24_test_once(monkeypatch, tmp_path):
    from scripts import run_final_evaluation as rfe

    calls: list[str] = []

    def fake_eval(config, ckpt, split="validation", **kw):
        calls.append(split)
        return _fake_id_result()

    monkeypatch.setattr(rfe, "load_yaml", lambda p: {"seed": 2026})
    monkeypatch.setattr(rfe, "resolve_checkpoint", lambda p: "unused.pt")
    monkeypatch.setattr(rfe, "evaluate_rml24", fake_eval)

    _run(monkeypatch, rfe, tmp_path)
    assert calls == ["test"]  # exactly one ID test inference


def test_closed_set_only_never_calls_any_ood_function(monkeypatch, tmp_path):
    from scripts import run_final_evaluation as rfe
    from evaluation import evaluate_ood as eo

    def boom(*a, **k):
        raise AssertionError("OOD path must not be called in closed-set-only mode")

    _patch_pure(monkeypatch, rfe)
    for name in ("evaluate_ood_final_rml24", "evaluate_ood_12class",
                 "read_threshold_manifest", "acquire_gate", "complete_gate",
                 "fake_int8_report_rml24", "evaluate_rml24_channel_ood"):
        monkeypatch.setattr(rfe, name, boom)
    for name in ("calibrate_ood_thresholds", "score_ood_final", "evaluate_ood_rml24",
                 "generate_ood_records", "run_model_logits"):
        if hasattr(eo, name):
            monkeypatch.setattr(eo, name, boom)

    _run(monkeypatch, rfe, tmp_path)  # must not raise


def test_closed_set_only_has_no_threshold_manifest_parameter():
    import inspect

    from scripts import run_final_evaluation as rfe

    sig = inspect.signature(rfe.run_closed_set_final_evaluation)
    assert "threshold_manifest" not in sig.parameters
    assert "threshold_manifest_path" not in sig.parameters


def test_missing_checkpoint_manifest_fails_closed(monkeypatch, tmp_path):
    from scripts import run_final_evaluation as rfe

    monkeypatch.setattr(rfe, "load_yaml", lambda p: {"seed": 2026})
    monkeypatch.setattr(rfe, "resolve_checkpoint", lambda p: "unused.pt")

    gate = tmp_path / "gate.json"
    with pytest.raises(FileNotFoundError):
        rfe.run_closed_set_final_evaluation(
            "cfg", str(tmp_path / "nope.json"),
            output=str(tmp_path / "out.json"), report_md=str(tmp_path / "report.md"),
            gate_path=str(gate), run_id="t",
        )
    assert not gate.exists()  # gate never acquired


def test_checkpoint_sha_mismatch_fails_closed(monkeypatch, tmp_path):
    from scripts import run_final_evaluation as rfe

    monkeypatch.setattr(rfe, "load_yaml", lambda p: {"seed": 2026})
    # Real resolve_checkpoint (not monkeypatched): the checkpoint file exists but the
    # manifest records a different SHA, so the run must fail closed before the gate.
    ckpt = tmp_path / "best.pt"
    ckpt.write_bytes(b"fake-checkpoint-bytes")
    manifest = _final_manifest()
    manifest["checkpoint_path"] = str(ckpt)
    manifest["checkpoint_sha256"] = "f" * 64  # wrong
    mp = tmp_path / "final_checkpoint_manifest.json"
    mp.write_text(json.dumps(manifest), encoding="utf-8")

    gate = tmp_path / "gate.json"
    with pytest.raises(RuntimeError):
        rfe.run_closed_set_final_evaluation(
            "cfg", str(mp), output=str(tmp_path / "out.json"),
            report_md=str(tmp_path / "report.md"), gate_path=str(gate), run_id="t",
        )
    assert not gate.exists()


def test_second_closed_set_run_rejected(monkeypatch, tmp_path):
    from scripts import run_final_evaluation as rfe

    _patch_pure(monkeypatch, rfe)
    _run(monkeypatch, rfe, tmp_path, run_id="t1")
    with pytest.raises(RuntimeError):
        _run(monkeypatch, rfe, tmp_path, run_id="t2")


def test_started_gate_rejects_duplicate_acquire(tmp_path):
    from evaluation.closed_set_gate import acquire_closed_set_gate, complete_closed_set_gate

    gate = tmp_path / "gate.json"
    kwargs = dict(checkpoint_path="p", checkpoint_sha256="b" * 64,
                  dataset_sha256="c" * 64, label_contract_sha256="a" * 64,
                  config_sha256="d" * 64)
    acquire_closed_set_gate(gate, run_id="r1", **kwargs)
    with pytest.raises(RuntimeError):  # STARTED already claimed
        acquire_closed_set_gate(gate, run_id="r2", **kwargs)
    complete_closed_set_gate(gate, output_sha256="e" * 64)
    with pytest.raises(RuntimeError):  # COMPLETE still blocks
        acquire_closed_set_gate(gate, run_id="r3", **kwargs)


def test_closed_set_gate_independent_of_ood_ledger(monkeypatch, tmp_path):
    from scripts import run_final_evaluation as rfe

    def ood_ledger_boom(*a, **k):
        raise AssertionError("OOD final ledger must not be claimed by closed-set mode")

    _patch_pure(monkeypatch, rfe)
    monkeypatch.setattr(rfe, "acquire_gate", ood_ledger_boom)
    monkeypatch.setattr(rfe, "complete_gate", ood_ledger_boom)

    _run(monkeypatch, rfe, tmp_path)  # must not raise -> OOD ledger never claimed
    assert not (tmp_path / "final_test_access.json").exists()


def test_report_contains_24_real_labels():
    from scripts import run_final_evaluation as rfe

    report = rfe.build_closed_set_report(_fake_id_result(), _final_manifest(), "unused.pt", "run")
    assert report["classes"] == list(LABEL_ORDER_24)
    assert [e["class"] for e in report["per_class"]] == list(LABEL_ORDER_24)
    assert all(e["class"] in LABEL_ORDER_24 for e in report["top_confusions"])
    assert all(e["top_confused_with"] in LABEL_ORDER_24 for e in report["top_confusions"])
    assert all(e["class"] in LABEL_ORDER_24 for e in report["top5_weakest"])


def test_report_confusion_matrix_is_24x24():
    from scripts import run_final_evaluation as rfe

    idr = _fake_id_result()
    report = rfe.build_closed_set_report(idr, _final_manifest(), "unused.pt", "run")
    cm = report["confusion_matrix"]
    assert len(cm) == 24
    assert all(len(row) == 24 for row in cm)
    labels = idr["labels"]
    for i in range(24):
        assert sum(cm[i]) == int(np.sum(labels == i))
    assert sum(sum(row) for row in cm) == len(labels)


def test_report_ood_final_test_accessed_false(monkeypatch, tmp_path):
    from scripts import run_final_evaluation as rfe

    _patch_pure(monkeypatch, rfe)
    report = _run(monkeypatch, rfe, tmp_path)
    assert report["ood_final_test_accessed"] is False
    assert report["final_blind_test_accessed"] is True

    ledger = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
    assert ledger["ood_final_test_accessed"] is False
    assert ledger["mode"] == "closed_set_only"
    assert ledger["output_sha256"] == rfe.file_sha256(tmp_path / "out.json")


def test_label_contract_sha_mismatch_fails_closed():
    from scripts import run_final_evaluation as rfe

    manifest = _final_manifest()
    manifest["label_contract_sha256"] = "e" * 64
    with pytest.raises(RuntimeError):
        rfe._verify_closed_set_identity(manifest)

    bad = _final_manifest()
    bad["dataset_sha256"] = "short"
    with pytest.raises(RuntimeError):
        rfe._verify_closed_set_identity(bad)


def test_closed_set_gate_records_all_identity_shas(monkeypatch, tmp_path):
    from scripts import run_final_evaluation as rfe

    _patch_pure(monkeypatch, rfe)
    manifest = _final_manifest()
    _run(monkeypatch, rfe, tmp_path)

    ledger = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
    assert ledger["schema_version"] == 1
    assert ledger["mode"] == "closed_set_only"
    assert ledger["checkpoint_sha256"] == manifest["checkpoint_sha256"]
    assert ledger["dataset_sha256"] == manifest["dataset_sha256"]
    assert ledger["label_contract_sha256"] == manifest["label_contract_sha256"]
    assert ledger["config_sha256"] == manifest["config_sha256"]
    assert ledger["id_test_accessed"] is True
    assert ledger["ood_final_test_accessed"] is False
    assert ledger["status"] == "COMPLETE"
    assert ledger["completed_at"] is not None
