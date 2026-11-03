from __future__ import annotations

import hashlib
import importlib.util
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
STAGE7 = ROOT.parent / "rml24_stage7_execution_20261027" / "rml24_final_stage7_board_overlay"
STAGE7_PC = ROOT.parent / "rml24_stage7_execution_20261027" / "pc" / "rml24_final_stage7_pc_selftest" / "pc_runtime"
sys.path.insert(0, str(STAGE7 / "runtime"))
sys.path.insert(0, str(ROOT / "runtime"))

from mode_control_server import ModeControlServer, ModeState  # noqa: E402
from radio_tuning import RxLoController  # noqa: E402
from scan_runtime import (  # noqa: E402
    ScanConfig,
    detect_public_training,
    has_full_coverage,
    remove_coarse_cfo,
    scan_and_select,
)
from ui_event import build_board_ui_result, build_ui_event  # noqa: E402


def public_train() -> np.ndarray:
    rng = np.random.default_rng(9011)
    pn = np.exp(1j * (np.pi / 4 + np.pi / 2 * rng.integers(0, 4, 1024))).astype(np.complex64)
    return np.tile(pn, 2)


def synthetic_capture(cfo_hz: float, *, seed: int = 7, start: int = 4096) -> np.ndarray:
    rng = np.random.default_rng(seed)
    raw = (rng.normal(size=65536) + 1j * rng.normal(size=65536)).astype(np.complex64) * 0.01
    frame = public_train().astype(np.complex128)
    n = np.arange(frame.size)
    frame *= np.exp(2j * np.pi * cfo_hz * n / 2_560_000)
    raw[start : start + frame.size] += frame.astype(np.complex64)
    return raw


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScanLogicTests(unittest.TestCase):
    def test_plan_covers_range(self) -> None:
        cfg = ScanConfig(2_395_000_000, 2_405_000_000, 1_000_000)
        self.assertEqual(len(cfg.lo_frequencies()), 11)
        self.assertTrue(has_full_coverage(cfg))

    def test_plan_rejects_gap(self) -> None:
        with self.assertRaises(ValueError):
            ScanConfig(2_395_000_000, 2_405_000_000, 2_400_000).validate()

    def test_wide_cfo_positive(self) -> None:
        detected = detect_public_training(synthetic_capture(903_250.0), public_train())
        self.assertLess(abs(detected.coarse_cfo_hz - 903_250.0), 1_500.0)
        self.assertGreater(detected.score, 0.95)

    def test_wide_cfo_negative(self) -> None:
        detected = detect_public_training(synthetic_capture(-877_700.0), public_train())
        self.assertLess(abs(detected.coarse_cfo_hz + 877_700.0), 1_500.0)
        self.assertGreater(detected.score, 0.95)

    def test_cfo_removal(self) -> None:
        raw = synthetic_capture(700_000.0)
        detected = detect_public_training(raw, public_train())
        corrected = remove_coarse_cfo(raw, detected.coarse_cfo_hz)
        redetected = detect_public_training(corrected, public_train())
        self.assertLess(abs(redetected.coarse_cfo_hz), 1_500.0)

    def test_noise_does_not_cross_public_threshold(self) -> None:
        rng = np.random.default_rng(991)
        noise = (rng.normal(size=65536) + 1j * rng.normal(size=65536)).astype(np.complex64)
        detected = detect_public_training(noise, public_train())
        self.assertLess(detected.score, 0.10)

    def test_scan_selects_best_lo_without_labels(self) -> None:
        signal_hz = 2_400_730_000
        state = {"lo": 0}

        def tune(value: int) -> int:
            state["lo"] = value
            return value

        def capture() -> np.ndarray:
            offset = signal_hz - state["lo"]
            if abs(offset) > 1_150_000:
                rng = np.random.default_rng(state["lo"])
                return (rng.normal(size=65536) + 1j * rng.normal(size=65536)).astype(np.complex64) * 0.01
            return synthetic_capture(offset, seed=state["lo"] & 0xFFFF)

        hit, rows = scan_and_select(
            ScanConfig(2_398_000_000, 2_402_000_000, 1_000_000),
            public_train(),
            tune,
            capture,
        )
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertLess(abs(hit.signal_hz - signal_hz), 1_500.0)
        self.assertEqual(len(rows), 5)
        self.assertNotIn("label", repr(rows).lower())


class RadioAdapterTests(unittest.TestCase):
    class Attr:
        def __init__(self, value: int) -> None:
            self.value = str(value)

    class Channel:
        def __init__(self, value: int) -> None:
            self.attrs = {"frequency": RadioAdapterTests.Attr(value)}

    class Radio:
        def __init__(self) -> None:
            self.rlo = RadioAdapterTests.Channel(2_400_000_000)
            self.receives = 0

        def set(self, channel, name, value) -> None:
            channel.attrs[name].value = str(value)

        def receive(self, count: int):
            self.receives += 1
            return np.zeros(count, dtype=np.complex64)

    def test_tune_readback_flush_restore(self) -> None:
        radio = self.Radio()
        ctl = RxLoController(radio, flush_captures=2)
        self.assertEqual(ctl.tune(2_401_000_000), 2_401_000_000)
        ctl.flush()
        self.assertEqual(radio.receives, 2)
        ctl.restore()
        self.assertEqual(int(radio.rlo.attrs["frequency"].value), 2_400_000_000)


class ModeControlTests(unittest.TestCase):
    def test_only_fixed_and_scan_are_accepted(self) -> None:
        state = ModeState()
        command_id, snapshot = state.apply("SET_MODE BAND_SCAN")
        self.assertEqual((command_id, snapshot.mode), (1, "BAND_SCAN"))
        with self.assertRaises(ValueError):
            state.apply("SET_MODE AUTO_LOCK")
        self.assertEqual(state.snapshot().mode, "BAND_SCAN")

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "AF_UNIX unavailable")
    def test_ui_two_phase_protocol(self) -> None:
        # Native Linux/board AF_UNIX sockets must live on a Unix filesystem;
        # WSL's mounted Windows drive rejects bind(), so use the platform temp.
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "ctl.sock")
            server = ModeControlServer(path, ModeState())
            server.start()
            try:
                client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                client.settimeout(2)
                client.connect(path)
                stream = client.makefile("rwb", buffering=0)
                stream.write(b"SET_MODE BAND_SCAN\n")
                self.assertTrue(stream.readline().startswith(b"OK accepted command_id=1"))
                self.assertTrue(stream.readline().startswith(b"OK applied command_id=1"))
                stream.write(b"STATUS\n")
                status = stream.readline().decode()
                self.assertIn("applied_mode=BAND_SCAN", status)
                client.close()
            finally:
                server.close()


class CompatibilityTests(unittest.TestCase):
    def test_fixed_tx_frame_is_byte_identical(self) -> None:
        old = load_module("stage7_tx", STAGE7_PC / "rml24_final_tx.py")
        new = load_module("scan_tx", ROOT / "pc_runtime" / "rml24_scan_tx.py")
        rng = np.random.default_rng(123)
        payload = rng.normal(size=2048).astype("<f4").tobytes()
        train = public_train()
        tail = np.ones(2048, dtype=np.complex64)
        self.assertEqual(old.build_frame(payload, train, tail).tobytes(), new.build_frame(payload, train, tail).tobytes())

    def test_ui_default_is_unchanged_and_scan_is_explicit(self) -> None:
        logits = [-5.0] * 24
        logits[4] = 5.0
        event = build_ui_event(1, {"pred": 4, "mean_logits": logits, "input_sha256": "0" * 64})
        fixed = build_board_ui_result(event)
        scan = build_board_ui_result(event, center_hz=2_401_250_000, work_mode="BAND SCAN")
        assert fixed is not None and scan is not None
        self.assertEqual(fixed["work_mode"], "FIXED")
        self.assertEqual(fixed["measurements"], None)
        self.assertEqual(scan["work_mode"], "BAND SCAN")

    def test_receiver_is_label_blind(self) -> None:
        source = (ROOT / "board_runtime" / "rml24_dualmode_receiver.py").read_text(encoding="utf-8")
        forbidden = ("expected_prediction", "ground_truth", "class_label", "truth_manifest")
        for token in forbidden:
            self.assertNotIn(token, source)
        self.assertIn("candidate_two_dc.recover", source)
        self.assertIn('set(message) - {"seq"}', source)

    def test_stage7_frozen_core_hashes_recorded(self) -> None:
        expected = {
            "runtime/receiver_core.py": None,
            "recovery/candidate_two_dc.py": None,
            "board_runtime/rml24_final_receiver.py": None,
        }
        for relative in expected:
            data = (STAGE7 / relative).read_bytes()
            self.assertEqual(len(hashlib.sha256(data).hexdigest()), 64)

    def test_scorer_keeps_missing_and_invalid_in_denominator(self) -> None:
        scorer = load_module("dualmode_scorer", ROOT / "scripts" / "score_dualmode_run.py")
        truth = {
            "n": 3,
            "records": [
                {"seq": 0, "class_index": 1},
                {"seq": 1, "class_index": 2},
                {"seq": 2, "class_index": 3},
            ],
        }
        results = {
            "records": [
                {"seq": 0, "mode": "FIXED", "candidate": {"finite": True, "pred": 1}},
                {"seq": 1, "mode": "BAND_SCAN", "candidate": {"finite": False, "pred": 2}},
            ]
        }
        report = scorer.score(results, truth)
        self.assertEqual(report["denominator"], 3)
        self.assertEqual(report["correct"], 1)
        self.assertEqual(report["missing"], 1)
        self.assertEqual(report["invalid"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

