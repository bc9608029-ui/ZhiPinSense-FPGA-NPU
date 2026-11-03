"""Status red-line tests: no forbidden PASS marker is emitted anywhere.

The frozen forbidden markers may only appear inside the contract module's
``FORBIDDEN_STATUS_MARKERS`` definition and in the documentation (which enumerates
them).  No module or shell script may print/assign one as an actual status.
"""
from pathlib import Path

from contracts import m25b_24class_contract as c

ROOT = Path(__file__).resolve().parents[1]
_CONTRACT = ROOT / "contracts" / "m25b_24class_contract.py"


def _iter_source_files():
    for ext in ("*.py", "*.sh"):
        for p in sorted(ROOT.rglob(ext)):
            parts = set(p.parts)
            if "dist" in parts or "__pycache__" in parts:
                continue
            if p.suffix == ".py" and p.name.startswith("test_"):
                continue  # this test itself iterates the markers
            yield p


def test_no_forbidden_marker_outside_contract():
    offenders = []
    for p in _iter_source_files():
        text = p.read_text(encoding="utf-8", errors="ignore")
        for marker in c.FORBIDDEN_STATUS_MARKERS:
            if marker in text and p != _CONTRACT:
                offenders.append(f"{p}:{marker}")
    assert not offenders, offenders


def test_honest_status_markers_present():
    # The honest ceiling markers must be defined (never the forbidden PASS ones).
    for marker in (
        c.BASELINE_NOT_FROZEN_MARKER,
        c.OE_MODEL_NOT_TRAINED_MARKER,
        c.OE_FRAMEWORK_READY_MARKER,
    ):
        assert marker
    assert "PASS" not in c.BASELINE_NOT_FROZEN_MARKER
    assert "PASS" not in c.OE_MODEL_NOT_TRAINED_MARKER


def test_forbidden_markers_are_all_pass_like():
    # Every forbidden marker claims a PASS / COMPLETE / DEPLOYMENT state.
    for marker in c.FORBIDDEN_STATUS_MARKERS:
        assert ("PASS" in marker) or ("COMPLETE" in marker) or ("DEPLOYMENT" in marker)
