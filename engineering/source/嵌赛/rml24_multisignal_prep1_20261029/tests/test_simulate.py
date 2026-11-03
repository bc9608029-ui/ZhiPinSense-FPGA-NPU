"""End-to-end offline scan simulation across the frozen test matrix."""

import math

from src.scoring import GroundTruthTarget, score
from src.simulate import Simulator

START = 2_399_000_000
STOP = 2_401_000_000
STEP = 1_000_000


def _truth(*specs):
    return [
        GroundTruthTarget(tid, hz, cls, entry, exit_, power_db=power)
        for tid, hz, cls, entry, exit_, power in specs
    ]


def _classifier_from_truth(truth, wrong=False):
    def classify(center_hz, iq):
        best = min(truth, key=lambda t: abs(t.center_hz - center_hz))
        name = "WRONG_CLASS" if wrong else best.class_name
        return [{"class_name": name, "confidence": 0.9}], 0.9
    return classify


def _run(truth, cycles=2, wrong=False):
    sim = Simulator(START, STOP, STEP, truth)
    sim.run(cycles, 1.0, _classifier_from_truth(truth, wrong))
    return sim, score(truth, sim.observations)


def test_zero_targets():
    sim = Simulator(START, STOP, STEP, [])
    sim.run(2, 1.0)
    assert sim.tracker.active_targets() == []
    assert sim.observations == []


def test_one_target():
    truth = _truth((1, 2_400_000_000, "QPSK", 0.0, math.inf, 30.0))
    sim, rep = _run(truth)
    assert rep.detection_rate == 1.0
    assert rep.missed_truth_ids == []
    assert rep.classification.correct == 1


def test_two_targets_frequency_separated():
    truth = _truth(
        (1, 2_400_000_000, "QPSK", 0.0, math.inf, 30.0),
        (2, 2_400_250_000, "BPSK", 0.0, math.inf, 30.0),
    )
    sim, rep = _run(truth)
    assert rep.detection_rate == 1.0
    assert rep.missed_truth_ids == []
    assert rep.false_alarm_target_ids == []


def test_three_targets():
    truth = _truth(
        (1, 2_400_000_000, "QPSK", 0.0, math.inf, 30.0),
        (2, 2_400_250_000, "BPSK", 0.0, math.inf, 30.0),
        (3, 2_399_750_000, "8PSK", 0.0, math.inf, 30.0),
    )
    sim, rep = _run(truth)
    assert rep.detection_rate == 1.0
    assert rep.detected_targets == 3


def test_range_edge_targets():
    truth = _truth(
        (1, START, "FM", 0.0, math.inf, 30.0),
        (2, STOP, "GMSK", 0.0, math.inf, 30.0),
    )
    sim, rep = _run(truth)
    assert rep.detection_rate == 1.0
    assert rep.missed_truth_ids == []


def test_entry_and_exit_with_aging():
    truth = _truth((1, 2_400_000_000, "QPSK", 2.0, 4.0, 30.0))
    sim = Simulator(START, STOP, STEP, truth, aging_cycles=3)
    sim.run(6, 1.0, _classifier_from_truth(truth))
    rep = score(truth, sim.observations)
    assert rep.detection_rate == 1.0
    assert rep.first_discovery_seconds[1] == 0.0  # found at entry cycle 2
    # After cycles 4,5,6 the target is missing and finally expires.
    assert sim.tracker.active_targets() == []
    assert len(sim.tracker.history()) == 1


def test_different_powers_within_dynamic_range():
    truth = _truth(
        (1, 2_400_000_000, "QPSK", 0.0, math.inf, 40.0),
        (2, 2_400_250_000, "BPSK", 0.0, math.inf, 15.0),  # 25 dB below
    )
    sim, rep = _run(truth)
    assert rep.detection_rate == 1.0
    assert rep.missed_truth_ids == []


def test_unresolvable_close_pair_counts_as_miss():
    # Two signals 7.5 kHz apart (3 bins) merge; scoring honestly reports a miss.
    truth = _truth(
        (1, 2_400_000_000, "QPSK", 0.0, math.inf, 30.0),
        (2, 2_400_007_500, "BPSK", 0.0, math.inf, 30.0),
    )
    sim, rep = _run(truth)
    assert rep.detected_targets == 1
    assert rep.missed_truth_ids == [2]
    assert rep.detection_rate == 0.5


def test_wrong_classification_does_not_change_detection():
    truth = _truth((1, 2_400_000_000, "QPSK", 0.0, math.inf, 30.0))
    sim, rep = _run(truth, wrong=True)
    assert rep.detection_rate == 1.0
    assert rep.classification.correct == 0
    assert rep.classification.wrong == 1
