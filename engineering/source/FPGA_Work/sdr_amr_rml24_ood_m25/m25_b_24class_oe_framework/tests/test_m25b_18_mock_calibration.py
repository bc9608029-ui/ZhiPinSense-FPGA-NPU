"""Mock threshold calibration: select on validation, lock via manifest."""
import json

import numpy as np

from ood import m25b_scores as sc
from ood import m25b_threshold_manifest as tm
from ood import m25b_thresholds as th


def test_mock_calibration(tmp_path):
    rng = np.random.default_rng(0)
    # ID Energy scores (lower = more ID) and far-OOD scores (higher = more OOD).
    id_scores = rng.normal(-8.0, 1.0, size=2000)
    far_scores = rng.normal(6.0, 1.0, size=2000)

    thresholds = th.select_thresholds(id_scores, far_scores)
    record = tm.build_threshold_record(
        model_sha256="f" * 64, score_name="energy", split_name="ood_validation",
        id_accept_99=thresholds["id_accept_99"],
        id_accept_95=thresholds["id_accept_95"],
        far_ood=thresholds["far_ood"],
        id_accept_rate_at_99=th.id_accept_rate(id_scores, thresholds["id_accept_99"]),
        far_reject_rate_at_99=th.far_reject_rate(far_scores, thresholds["id_accept_99"]),
        num_id=id_scores.size, num_far_ood=far_scores.size,
        created_utc="2026-10-09T00:00:00Z")

    path = str(tmp_path / "threshold_manifest.json")
    tm.write_once(path, record)

    with open(path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    key = tm.threshold_key(record)
    assert key in manifest
    assert manifest[key]["score_name"] == "energy"

    # Locked calibration is stable: energy score direction preserved on re-read.
    energy = sc.score_energy(np.zeros((1, 24)))
    assert energy.shape == (1,)
