#!/usr/bin/env python3
"""fix3_recovery.py -- byte-exact host reconstruction of the board fix2 recovery.

Fix3 = M29-RML24-FIX10CLASS24-INDEPENDENT-RX-PAYLOAD-FIDELITY-FIX3.  This module
re-implements, in numpy/double, the exact arithmetic of the board's public
recovery chain (board_package/radioml_independent_rx_public_recovery.hpp,
estimate_public_reference + recover_model_input with the v2 amplitude contract
unscale = 1/71.609111379029812).  It is the substrate for Phase B/C analysis.

Faithfulness is pinned by construction and by a test: `recover_v2` reproduces the
board's persisted `N.recovered.tensor.bin` SHA-256 for all 24 frames of the
`rml24_fix2_dual_1773374951_244` capture (24/24, verified).

The recovery reads ONLY the burst + the public reference (ZC preamble/tail +
16QAM training block).  It never reads original payload IQ / labels / source ID
to choose parameters.  The payload-DC measurements exported here are diagnostic
(offline only) and are NOT fed back into any candidate fix.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
import sys
from pathlib import Path

import numpy as np

# Import the frozen contract + the board's fix2 reference (read-only).
_CONTRACT_DIR = r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\scripts"
_FIX2_DIR = r"F:\嵌赛\fix10class24_independent_rx_recovery_fix2_work\scripts"
for _p in (_CONTRACT_DIR, _FIX2_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import radioml_independent_rx_contract as IRX  # noqa: E402
import radioml_dualsdr_common as C           # noqa: E402
from reproduce_fix2_diagnosis import (       # noqa: E402
    read_raw_i16, locate_preamble, FS, K_TOTAL)
from radioml_independent_rx_recovery_fix2 import (  # noqa: E402
    estimate_public_reference_fix2, frac_delay_sinc)

# Frozen v2 amplitude contract (source_id = fix1v2-waveform-corrected-24waveforms).
V2_TX_SCALE = 71.609111379029812
V2_UNSCALE = 1.0 / V2_TX_SCALE

# iqrftrain::kPi (frozen) -- identical to the double M_PI used by numpy.
PI = 3.141592653589793238462643383279502884

# Burst layout (iq_rf_training_frame.hpp, frozen).
SETTLE_START, SETTLE_END = 1024, 2048          # settling-zero (silence)
TRAIN_START, TRAIN_END = 2048, 3072            # 16QAM training block
PAYLOAD_START = 3072                           # payload start
PAYLOAD_END = PAYLOAD_START + 53760            # payload end (56832)
GUARD_START, GUARD_END = PAYLOAD_END, 58880    # guard-zero (silence, 2048)
TAIL_START, TAIL_END = 58880, 59904            # ZC tail

MODEL_WINDOW = IRX.GEN.SAMPLE_LENGTH           # 1024


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def derot(x: np.ndarray, cfo: float, start: int = 0) -> np.ndarray:
    """De-rotate by CFO using explicit cos/sin (byte-exact with the C++ std::cos/sin)."""
    n = np.arange(len(x), dtype=np.float64) + start
    ph = -2.0 * PI * cfo * n / FS
    return x * (np.cos(ph) + 1j * np.sin(ph))


def wide_linear_inverse(r: np.ndarray, a: complex, b: complex) -> np.ndarray:
    """x = (conj(a)*r - b*conj(r)) / (|a|^2 - |b|^2), byte-exact with the C++."""
    return IRX.wide_linear_inverse(r, a, b)


def load_burst(capture_dir: Path, sid: int) -> tuple[np.ndarray, int]:
    """Read raw.i16 -> deinterleave -> locate preamble -> slice the 59904 burst."""
    inter = read_raw_i16(capture_dir / ("%d.raw.i16" % sid))
    rx_full = C.deinterleave_int16(inter)
    off, _ = locate_preamble(rx_full, len(rx_full) - K_TOTAL)
    rx_burst = rx_full[off:off + K_TOTAL].copy()
    return rx_burst, off


def aligned_burst(rx_burst: np.ndarray, est: dict) -> np.ndarray:
    return np.roll(rx_burst, -est["timing_offset"]) if est["timing_offset"] else rx_burst


def recover_v2(rx_burst: np.ndarray, est: dict) -> np.ndarray:
    """Faithful fix2 recovery with v2 unscale (byte-exact with the board tensor)."""
    aligned = aligned_burst(rx_burst, est)
    rx_derot = derot(aligned, est["coarse_cfo_hz"])
    payload = rx_derot[PAYLOAD_START:PAYLOAD_END]
    wl = wide_linear_inverse(payload, est["a"], est["b"])
    shifted = frac_delay_sinc(wl, -est["fractional_timing"])
    return shifted[:MODEL_WINDOW] * V2_UNSCALE


def recover_v2_with_dc(rx_burst: np.ndarray, est: dict, dc: complex) -> np.ndarray:
    """Recovery after subtracting a category-independent complex DC `dc` pre-de-rotation."""
    aligned = aligned_burst(rx_burst, est)
    aligned = aligned - dc
    rx_derot = derot(aligned, est["coarse_cfo_hz"])
    payload = rx_derot[PAYLOAD_START:PAYLOAD_END]
    wl = wide_linear_inverse(payload, est["a"], est["b"])
    shifted = frac_delay_sinc(wl, -est["fractional_timing"])
    return shifted[:MODEL_WINDOW] * V2_UNSCALE


def tensor_to_bytes(iq: np.ndarray) -> bytes:
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    x = np.empty((2, len(iq)), dtype="<f4")
    x[0] = iq.real.astype("<f4")
    x[1] = iq.imag.astype("<f4")
    return x.tobytes()


def load_tensor(path: Path) -> np.ndarray:
    """Load a planar [2,1024] f32 tensor (orig/recovered .bin) as complex128."""
    a = np.frombuffer(path.read_bytes(), dtype="<f4")
    return a[:MODEL_WINDOW] + 1j * a[MODEL_WINDOW:]


def run_host_infer(icraft_run: Path, model_json: Path, model_raw: Path,
                   iq: np.ndarray) -> np.ndarray:
    """Run icraft-run Host backend; return the 24 raw logits as fp32 ndarray."""
    x = np.empty((2, len(iq)), dtype="<f4")
    x[0] = iq.real.astype("<f4")
    x[1] = iq.imag.astype("<f4")
    with tempfile.TemporaryDirectory(prefix="fix3inf_") as td:
        wd = Path(td)
        inp = wd / "input.bin"
        inp.write_bytes(x.tobytes())
        lp = wd / "logs"
        cmd = [str(icraft_run), "--json", str(model_json), "--raw", str(model_raw),
               "--network", "model_24class", "--input", str(inp),
               "--backends", "Host", "--dump_output", "--log_path", str(lp)]
        proc = subprocess.run(cmd, cwd=str(wd), capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError("icraft-run exit %d: %s"
                               % (proc.returncode, proc.stderr.decode("utf-8", "replace")[-2000:]))
        ftmp_dir = lp / "model_24class" / "ftmpHQB"
        ftmps = list(ftmp_dir.glob("*.ftmp")) if ftmp_dir.is_dir() else []
        if len(ftmps) != 1:
            raise RuntimeError("expected 1 ftmp, got %d" % len(ftmps))
        return np.frombuffer(ftmps[0].read_bytes(), dtype="<f4").astype(np.float64)
