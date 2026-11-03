"""Target identity, de-duplication and aging (contract sec. 7)."""

from src.tracker import TargetTracker


def test_first_observation_is_new():
    tr = TargetTracker()
    rec = tr.observe(2_400_000_000, 10.0)
    assert rec.target_id == 1
    assert rec.status == "new"
    assert rec.center_hz == 2_400_000_000


def test_redetection_within_merge_radius_keeps_identity():
    tr = TargetTracker()
    a = tr.observe(2_400_000_000, 10.0)
    b = tr.observe(2_400_005_000, 11.0)   # 5 kHz < merge radius 6.25 kHz
    assert b.target_id == a.target_id
    assert b.status == "tracking"
    assert b.last_seen == 11.0
    assert b.center_hz == 2_400_005_000


def test_distant_detection_is_a_new_target():
    tr = TargetTracker()
    a = tr.observe(2_400_000_000, 10.0)
    b = tr.observe(2_400_250_000, 11.0)
    assert b.target_id == a.target_id + 1


def test_target_id_is_never_reused_after_aging():
    tr = TargetTracker(aging_cycles=3)
    tr.observe(2_400_000_000, 10.0)
    for _ in range(3):
        tr.end_cycle()
    assert tr.active_targets() == []
    rec = tr.observe(2_400_000_000, 20.0)
    assert rec.target_id == 2  # never reused


def test_aging_marks_missing_then_expires():
    tr = TargetTracker(aging_cycles=3)
    rec = tr.observe(2_400_000_000, 10.0)
    tr.end_cycle()
    assert tr.active_targets()[0].status == "missing"
    tr.end_cycle()
    assert tr.active_targets()[0].status == "missing"
    expired = tr.end_cycle()
    assert len(expired) == 1
    assert expired[0].target_id == rec.target_id
    assert tr.active_targets() == []


def test_classify_sets_top3_and_confidence():
    tr = TargetTracker()
    rec = tr.observe(2_400_000_000, 10.0)
    top3 = [
        {"class_name": "QPSK", "confidence": 0.8},
        {"class_name": "BPSK", "confidence": 0.1},
        {"class_name": "8PSK", "confidence": 0.05},
    ]
    tr.classify(rec.target_id, top3, 0.8)
    got = tr.active_targets()[0]
    assert got.top3 == top3
    assert got.confidence == 0.8


def test_snapshot_is_frozen_nine_field_records():
    tr = TargetTracker()
    tr.observe(2_400_000_000, 10.0, bw_hz=8_000)
    rec = tr.snapshot()[0]
    assert set(rec.keys()) == {
        "target_id", "center_hz", "bw_hz", "power_valid", "top3",
        "confidence", "last_seen", "status", "backend",
    }
