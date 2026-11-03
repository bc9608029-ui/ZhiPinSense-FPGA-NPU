"""Scoring contract: detection vs classification separated, miss is an error."""

import math

from src.scoring import GroundTruthTarget, score


def _obs(target_id, center_hz, last_seen, class_name, confidence=0.9):
    return {
        "target_id": target_id,
        "center_hz": center_hz,
        "last_seen": last_seen,
        "top3": [{"class_name": class_name, "confidence": confidence}],
        "confidence": confidence,
    }


def _truth(*ids_hz_class):
    return [
        GroundTruthTarget(tid, hz, cls, 0.0, math.inf, power_db=30.0)
        for tid, hz, cls in ids_hz_class
    ]


def test_full_detection_perfect_classification():
    truth = _truth((1, 2_400_000_000, "QPSK"), (2, 2_400_250_000, "BPSK"))
    obs = [
        _obs(1, 2_400_000_000, 1.0, "QPSK"),
        _obs(2, 2_400_250_000, 1.0, "BPSK"),
    ]
    r = score(truth, obs)
    assert r.detection_rate == 1.0
    assert r.missed_truth_ids == []
    assert r.false_alarm_target_ids == []
    assert r.classification.correct == 2
    assert r.classification.classified == 2
    assert r.classification.accuracy == 1.0


def test_miss_is_a_fixed_error():
    truth = _truth((1, 2_400_000_000, "QPSK"), (2, 2_400_250_000, "BPSK"))
    obs = [_obs(1, 2_400_000_000, 1.0, "QPSK")]
    r = score(truth, obs)
    assert r.detected_targets == 1
    assert r.expected_targets == 2
    assert r.detection_rate == 0.5
    assert r.missed_truth_ids == [2]


def test_false_alarm_is_reported_separately():
    truth = _truth((1, 2_400_000_000, "QPSK"))
    obs = [
        _obs(1, 2_400_000_000, 1.0, "QPSK"),
        _obs(2, 2_400_750_000, 1.0, "FM"),  # no truth here
    ]
    r = score(truth, obs)
    assert r.detection_rate == 1.0
    assert r.false_alarm_target_ids == [2]


def test_duplicate_targets_detected():
    truth = _truth((1, 2_400_000_000, "QPSK"))
    obs = [
        _obs(1, 2_400_000_000, 1.0, "QPSK"),
        _obs(2, 2_400_002_000, 1.0, "QPSK"),  # tracker should have merged these
    ]
    r = score(truth, obs)
    assert len(r.duplicate_groups) == 1
    assert r.duplicate_groups[0]["truth_id"] == 1


def test_wrong_classification_reported_separately_from_detection():
    truth = _truth((1, 2_400_000_000, "QPSK"))
    obs = [_obs(1, 2_400_000_000, 1.0, "BPSK")]  # detected, mis-classified
    r = score(truth, obs)
    assert r.detection_rate == 1.0           # detection unaffected
    assert r.classification.correct == 0
    assert r.classification.wrong == 1
    assert r.classification.accuracy == 0.0


def test_unclassified_matched_target_not_counted_as_correct():
    truth = _truth((1, 2_400_000_000, "QPSK"))
    obs = [{"target_id": 1, "center_hz": 2_400_000_000,
            "last_seen": 1.0, "top3": [], "confidence": 0.0}]
    r = score(truth, obs)
    assert r.detection_rate == 1.0
    assert r.classification.classified == 0
    assert r.classification.unclassified_matched == 1


def test_first_discovery_delay_and_revisit_intervals():
    truth = _truth((1, 2_400_000_000, "QPSK"))
    obs = [
        _obs(1, 2_400_000_000, 5.0, "QPSK"),
        _obs(1, 2_400_000_000, 8.0, "QPSK"),
        _obs(1, 2_400_000_000, 13.0, "QPSK"),
    ]
    r = score(truth, obs)
    assert r.first_discovery_seconds[1] == 5.0
    assert r.revisit_intervals_seconds[1] == [3.0, 5.0]
