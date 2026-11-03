"""The run_complete.sh step-6 verifier feeds ONE shared input to both models.

This guards the actual logic that the shell step exercises: a previous inlined
version called ``torch.randn`` twice and therefore always compared two different
inputs.  The shared verifier below generates a single tensor.
"""

from __future__ import annotations

from scripts.verify_qam_aware_v3_2_init import verify_init_matches_v2
from training.utils import PROJECT_ROOT


def test_verify_init_matches_v2_uses_single_shared_input() -> None:
    result = verify_init_matches_v2("configs/qam_aware_v3_2.yaml")
    assert result["init_logits_match_v2"] is True
    assert result["gate"] == 0.0
    assert result["max_abs_diff"] < 1e-5
    assert result["input"] == [8, 2, 1024]


def test_run_complete_calls_the_shared_verifier_not_two_randn_calls() -> None:
    script = (PROJECT_ROOT / "autodl_v3_2" / "run_complete.sh").read_text(encoding="utf-8")
    assert "scripts.verify_qam_aware_v3_2_init" in script
    # The buggy pattern fed two independently-drawn tensors to the two models.
    assert "v2(torch.randn" not in script
    assert "m(torch.randn" not in script
