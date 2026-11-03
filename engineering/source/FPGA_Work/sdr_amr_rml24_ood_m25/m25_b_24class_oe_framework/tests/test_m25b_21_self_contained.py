"""Self-containment tests: M25-B must not import the V1.1 project at runtime."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_cross_project_import_in_python():
    offenders = []
    for p in sorted(ROOT.rglob("*.py")):
        if "__pycache__" in p.parts or "dist" in p.parts:
            continue
        if p.name.startswith("test_"):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        # Any actual import statement referencing the V1.1 tree is runtime coupling.
        for line in text.splitlines():
            s = line.strip()
            if (s.startswith("import ") or s.startswith("from ")) and \
                    "sdr_amr_rml24_ood_v1" in s:
                offenders.append(f"{p}:{s}")
    assert not offenders, offenders


def test_no_v11_training_utils_import():
    offenders = []
    for p in sorted(ROOT.rglob("*.py")):
        if "__pycache__" in p.parts or "dist" in p.parts:
            continue
        if p.name.startswith("test_"):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("from training.utils") or s.startswith("import training.utils"):
                offenders.append(f"{p}:{s}")
    assert not offenders, offenders


def test_required_dependencies_limited():
    # Framework runtime depends only on numpy/scipy (+ torch/onnxruntime, lazily).
    for p in sorted(ROOT.rglob("*.py")):
        if "__pycache__" in p.parts or "dist" in p.parts or p.name.startswith("test_"):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("import optuna") or s.startswith("from optuna"):
                raise AssertionError(f"optuna imported eagerly in {p}: {s}")
