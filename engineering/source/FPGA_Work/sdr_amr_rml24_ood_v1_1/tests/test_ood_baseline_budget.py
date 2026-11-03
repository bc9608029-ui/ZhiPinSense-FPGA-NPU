"""V1.1 budget/dedup — OOD baselines never retrain (model_training_runs == 0)."""

from __future__ import annotations

from pathlib import Path


def test_ood_baseline_declares_zero_training_runs(monkeypatch, tmp_path: Path) -> None:
    from scripts import run_ood_baselines

    monkeypatch.setattr(run_ood_baselines, "evaluate_ood_rml24",
                        lambda *a, **k: {"families": {"energy": {}}})
    monkeypatch.setattr(run_ood_baselines, "load_yaml", lambda p: {"seed": 2026})
    written: dict = {}
    monkeypatch.setattr(run_ood_baselines, "save_json",
                        lambda data, path: written.update(data))

    report = run_ood_baselines.run_ood_baselines(
        "configs/rml24_base.yaml", "unused.pt",
        output_path=str(tmp_path / "ood_baselines.json"),
    )
    assert report["model_training_runs"] == 0
    assert written.get("model_training_runs") == 0
