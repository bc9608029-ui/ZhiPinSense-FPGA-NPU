"""Baseline-frozen gate tests (fail-closed toward NOT_FROZEN)."""
import json

from training import m25b_baseline_gate as g


def test_missing_manifest_not_frozen(tmp_path):
    path = str(tmp_path / "missing.json")
    status, manifest = g.baseline_status(path)
    assert status == g.NOT_FROZEN
    assert manifest is None


def test_incomplete_manifest_not_frozen(tmp_path):
    path = str(tmp_path / "partial.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"model_sha256": "a" * 64}, fh)
    status, manifest = g.baseline_status(path)
    assert status == g.NOT_FROZEN


def test_valid_manifest_frozen(tmp_path):
    path = str(tmp_path / "ok.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({
            "model_sha256": "a" * 64,
            "checkpoint_path": "artifacts/seed2026/best.pt",
            "label_order_sha256": "0814d7b5a522abacd1eb3052f89fb83a8e91f83cf53745e5a6b804dd1b85e3c8",
        }, fh)
    status, manifest = g.baseline_status(path)
    assert status == g.FROZEN
    assert manifest["model_sha256"] == "a" * 64


def test_require_baseline_prints_not_frozen(tmp_path, capsys):
    path = str(tmp_path / "missing.json")
    result = g.require_baseline(path)
    assert result is None
    out = capsys.readouterr().out
    assert g.NOT_FROZEN in out
