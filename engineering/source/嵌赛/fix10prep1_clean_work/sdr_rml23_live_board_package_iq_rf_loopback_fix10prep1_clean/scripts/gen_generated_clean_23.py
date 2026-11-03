#!/usr/bin/env python3
"""gen_generated_clean_23.py -- fix10-prep Stage 3 (Path B/C): generate the CLEAN
digital-baseline waveforms for the 23 deployed classes and run them through the
Route D2 reconstruction pipeline to produce the CI16 TX waveforms + the recovered
[2,1024] model-input tensors.

WHY this generator exists: the RadioML Route D2 artifacts are drawn from the REAL
HDF5 extraction (extract_radioml_stage_g.py) -- they carry measurement noise and
channel impairment.  Paths B and C of fix10-prep need a CONTROLLED, IMPAIRMENT-FREE
digital baseline so the dual-SDR RF path can be compared per-sample against a
clean reference (was the RF round-trip the thing that moved the model's mind, or
was it already gone in the digital preprocess?).  There is no in-tree 23-class
clean generator (syniq has only BPSK/QPSK/4ASK/16QAM; rf_waveform_12class has a
different 12-label set), so this synthesizes all 24 raw source classes from
scratch, reusing only the RRC/constellation math from syniq + the AM/FM/GMSK/OOK
algorithms from rf_waveform_12class as *references*, and the D2 reconstruction
primitives from analyze_route_d2_4ask.py verbatim.

AM-SSB "both included" (user decision 2026-10-15): deployed class 17 pools TWO raw
source classes -- 17 (AM-SSB-WC, with carrier) and 18 (AM-SSB-SC, suppressed
carrier) -- both map to deployed 17 via rml23::kSourceToDeployed.  The clean
generator therefore synthesizes all 24 raw source classes (24 x 30 = 720 files),
NOT 23 x 30 = 690, and keeps source_class 17/18 distinct for audit.  Every other
deployed class has exactly one raw source (raw 19/20/21/22/23 deploy to 18/19/20/
21/22).

Output contract (per file, matching build_route_d2_rf_artifacts.build_one):
    1024 complex @128 kSPS clean baseband (RMS == 1.0)
      -> AC-remove (subtract the signal's own DC)
      -> x20 Blackman-Harris-4 interpolation to 53760 complex @2.56 MSPS
      -> int16 interleaved CI16 (215040 bytes), AC scaled to global K == 2048
      -> recovered [2,1024] fp32 tensor (8192 bytes) = AC re-mapped + DC restored.

Two manifests are written:
  route_d2_rf_manifest.tsv  24 columns, byte-compatible with
                            iq_digital_loopback.hpp::load_d2_sidecar() -- this is
                            what the C++ clean runner (iq_clean_iq_23class_fix10.hpp)
                            loads, so it carries the per-file D2 restore constants
                            (original_dc_i/q, rec_scale) and both file SHAs.
  clean_manifest.tsv        11 columns (the fix10-prep §9 documented projection),
                            one row per written sample.

Determinism: every sample is generated from a fixed per-file seed derived from
(BASE_SEED, source_class, sample_index) via splitmix64.  Two runs with the same
arguments produce byte-identical CI16, tensors and manifests.

Never modifies any model/weights/labels/24->23 mapping/gate; never runs the NPU.
Pure stdlib + numpy.  Run isolated:  python -I gen_generated_clean_23.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_route_d2_4ask as A            # reconstruction primitives (reused)
import build_route_d2_rf_artifacts as B       # SOURCE_TO_DEPLOYED / DEPLOYED_NAMES

# ---- frozen clean-synthesis constants (documented; change == new freeze) -------
N_SAMPLES = A.N_SAMPLES                     # 1024
FS_BASE = 128000.0                          # clean baseband sample rate (Hz)
SPS = 8                                     # samples per symbol @128 kSPS
SYMBOL_RATE = FS_BASE / SPS                 # 16000 Hz
ROLLOFF = 0.35                              # RRC rolloff
SPAN = 8                                    # RRC span in symbols
GLOBAL_K = 2048.0                           # global int16 complex RMS target
EDGE = "zero"
GUARD = A.DEFAULT_GUARD                     # 832
SAMPLE_RATE_HZ = 2560000

BASE_SEED = 0x5EEDC1E4                       # master seed (frozen)
MASK64 = 0xFFFFFFFFFFFFFFFF

# AM message bandwidth (Hz) @128 kSPS (audio-band message, frozen).
AM_MSG_CUTOFF_HZ = 4000.0
AM_MOD_INDEX = 0.8                          # sideband/carrier ratio (m)
AM_CARRIER = 1.0                            # AM-DSB-WC / AM-SSB-WC carrier amp
FM_DEV_HZ = 8000.0                          # FM peak deviation (WBFM, beta~2)
GMSK_BT = 0.5                               # Gaussian BT (GMSK = MSK + Gaussian)
GMSK_MOD_INDEX = 0.5                        # MSK modulation index
OOK_ON = np.sqrt(2.0)                       # {0, sqrt(2)} unit-power on/off

SOURCE_TO_DEPLOYED = B.SOURCE_TO_DEPLOYED
DEPLOYED_NAMES = B.DEPLOYED_NAMES
INDEX_TO_CLASS = A.INDEX_TO_CLASS
SOURCE_CLASS_INDEX = A.SOURCE_CLASS_INDEX
N_SOURCE_CLASSES = len(SOURCE_CLASS_INDEX)  # 24

MANIFEST_HEADER = B.MANIFEST_HEADER        # 24-col route_d2_rf_manifest.tsv schema
CLEAN_MANIFEST_HEADER = ["source_index", "file_name", "modulation", "source_class",
                         "deployed_class", "complex_samples", "sample_rate",
                         "component_rms", "sha256", "seed", "split_role"]


# ---------------------------------------------------------------------------
# Deterministic RNG.
# ---------------------------------------------------------------------------
def splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & MASK64
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return (z ^ (z >> 31)) & MASK64


def file_seed(source_class: int, sample_index: int) -> int:
    """Deterministic per-file 64-bit seed from the frozen BASE_SEED.  Same tuple
    -> same seed -> byte-identical waveform, across runs and machines."""
    x = (BASE_SEED ^ (source_class * 0x9E3779B97F4A7C15)
         ^ (sample_index * 0xC2B2AE3D27D4EB4F)) & MASK64
    return splitmix64(x)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# RRC + pulse shaping (numpy re-implementation of syniq::rrc_coeffs/pulse_shape).
# ---------------------------------------------------------------------------
_rrc_cache: np.ndarray | None = None


def rrc_taps(sps: int = SPS, beta: float = ROLLOFF, span: int = SPAN) -> np.ndarray:
    global _rrc_cache
    if _rrc_cache is not None:
        return _rrc_cache
    n = span * sps
    h = np.empty(n + 1, np.float64)
    center = n / 2.0
    tc = 1.0 / (4.0 * beta)
    for i in range(n + 1):
        t = (i - center) / sps
        if abs(t) < 1e-9:
            h[i] = 1.0 - beta + 4.0 * beta / np.pi
        elif abs(abs(t) - tc) < 1e-9:
            h[i] = (beta / np.sqrt(2.0)) * (
                (1.0 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * beta)) +
                (1.0 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * beta)))
        else:
            num = (np.sin(np.pi * t * (1.0 - beta)) +
                   4.0 * beta * t * np.cos(np.pi * t * (1.0 + beta)))
            den = np.pi * t * (1.0 - (4.0 * beta * t) ** 2)
            h[i] = num / den
    scale = np.sqrt(np.sum(h * h) / sps)   # => sum(h^2) == sps
    h /= scale
    _rrc_cache = h
    return h


def pulse_shape(symbols: np.ndarray, n_out: int = N_SAMPLES,
                sps: int = SPS) -> np.ndarray:
    """RRC pulse-shape a unit-power symbol stream to n_out steady-state samples.
    Mirrors syniq::pulse_shape: group delay = (taps-1)/2 + (span/2)*sps, output
    length (n_symbols - span)*sps."""
    h = rrc_taps(sps)
    taps = h.size
    n_sym = n_out // sps + SPAN          # -> (n_out/sps)*sps == n_out steady-state
    y = np.zeros(n_sym * sps + taps - 1, np.complex128)
    for k in range(n_sym):
        base = k * sps
        y[base:base + taps] += symbols[k] * h
    start = (taps - 1) // 2 + (SPAN // 2) * sps
    return y[start:start + n_out]


def draw_symbols(rng: np.random.Generator, constellation: np.ndarray,
                 n_sym: int) -> np.ndarray:
    idx = rng.integers(0, constellation.size, n_sym)
    return constellation[idx]


def rms_normalize(x: np.ndarray) -> np.ndarray:
    rms = float(np.sqrt(np.mean(np.abs(x) ** 2)))
    if rms <= 0.0:
        return x
    return x / rms


# ---------------------------------------------------------------------------
# Constellations (unit average power E[|s|^2] == 1.0; frozen).
# ---------------------------------------------------------------------------
def _psk(M: int) -> np.ndarray:
    k = np.arange(M, dtype=np.float64)
    return np.exp(1j * 2.0 * np.pi * k / M)


def _pam_levels(bits: int) -> np.ndarray:
    """Bipolar PAM levels for `bits` bits per symbol, unit average power."""
    n = 2 ** bits
    levels = np.arange(-(n - 1), n, 2, dtype=np.float64)   # odd integers
    levels /= np.sqrt(np.mean(levels ** 2))
    return levels


def _qam_square(bits: int) -> np.ndarray:
    n_axis = 2 ** (bits // 2)
    levels = np.arange(-(n_axis - 1), n_axis, 2, dtype=np.float64)
    norm = np.sqrt(2.0 * np.mean(levels ** 2))
    I, Q = np.meshgrid(levels, levels)
    return ((I + 1j * Q) / norm).ravel()


def _qam_cross(bits: int) -> np.ndarray:
    if bits == 5:                       # 32QAM: 6x6 minus 4 corners
        levels = np.array([-5, -3, -1, 1, 3, 5], np.float64)
        remove = lambda i, q: abs(i) == 5 and abs(q) == 5
    elif bits == 7:                     # 128QAM: 12x12 minus 16-corner block
        levels = np.arange(-11, 12, 2, dtype=np.float64)
        remove = lambda i, q: abs(i) >= 9 and abs(q) >= 9
    else:
        raise ValueError("cross QAM only supports 32/128")
    pts = []
    for i in levels:
        for q in levels:
            if not remove(i, q):
                pts.append(i + 1j * q)
    pts = np.array(pts, np.complex128)
    pts /= np.sqrt(np.mean(np.abs(pts) ** 2))
    return pts


def _apsk(ring_counts: tuple) -> np.ndarray:
    radii = {
        2: [1.0, 2.85],                      # 16APSK
        3: [1.0, 2.84, 5.27],                # 32APSK
        4: [1.0, 2.5, 4.5, 6.5],             # 64APSK
        5: [1.0, 2.5, 4.0, 5.5, 7.0],        # 128APSK
    }
    R = radii[len(ring_counts)]
    pts = []
    for r, (cnt, radius) in enumerate(zip(ring_counts, R)):
        phase0 = (np.pi / cnt) if (r % 2 == 1) else 0.0
        for k in range(cnt):
            pts.append(radius * np.exp(1j * (phase0 + 2.0 * np.pi * k / cnt)))
    pts = np.array(pts, np.complex128)
    pts /= np.sqrt(np.mean(np.abs(pts) ** 2))
    return pts


_CONSTELLATIONS = {
    0:  np.array([0.0 + 0j, OOK_ON + 0j]),          # OOK {0, sqrt(2)}
    1:  _pam_levels(2),                             # 4ASK {+-1,+-3}/sqrt5
    2:  _pam_levels(3),                             # 8ASK {+-1..+-7}/sqrt21
    3:  np.array([1.0 + 0j, -1.0 + 0j]),            # BPSK
    4:  _psk(4),                                    # QPSK
    5:  _psk(8),                                    # 8PSK
    6:  _psk(16),                                   # 16PSK
    7:  _psk(32),                                   # 32PSK
    8:  _apsk((4, 12)),                             # 16APSK
    9:  _apsk((4, 12, 16)),                         # 32APSK
    10: _apsk((4, 12, 20, 28)),                     # 64APSK
    11: _apsk((4, 12, 20, 28, 64)),                 # 128APSK
    12: _qam_square(4),                             # 16QAM
    13: _qam_cross(5),                              # 32QAM
    14: _qam_square(6),                             # 64QAM
    15: _qam_cross(7),                              # 128QAM
    16: _qam_square(8),                             # 256QAM
}


# ---------------------------------------------------------------------------
# Analog / continuous-phase synthesis (references: rf_waveform_12class.hpp).
# ---------------------------------------------------------------------------
def _bandlimited_message(rng: np.random.Generator, n: int = N_SAMPLES) -> np.ndarray:
    """White Gaussian -> Hann-windowed-sinc lowpass -> mean-remove -> peak-normalize
    (audio-band message, mirroring the 12-class bandlimited AM/FM message)."""
    msg = rng.standard_normal(n)
    ntaps = 65
    fc = AM_MSG_CUTOFF_HZ / FS_BASE
    t = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = np.sinc(2.0 * fc * t) * np.hanning(ntaps)
    h /= h.sum()
    msg = np.convolve(msg, h, mode="same")
    msg -= msg.mean()
    peak = float(np.max(np.abs(msg)))
    if peak > 1e-12:
        msg /= peak
    return msg


def _analytic(x: np.ndarray) -> np.ndarray:
    """Analytic signal (single-sideband) via FFT, no scipy.  Upper sideband."""
    X = np.fft.fft(x)
    n = x.size
    h = np.zeros(n, np.complex128)
    h[0] = 1.0
    if n % 2 == 0:
        h[1:n // 2] = 2.0
        h[n // 2] = 1.0
    else:
        h[1:(n + 1) // 2] = 2.0
    return np.fft.ifft(X * h)


def _am_signal(rng: np.random.Generator, variant: str) -> np.ndarray:
    msg = _bandlimited_message(rng)
    if variant == "DSB-WC":
        return (AM_CARRIER + AM_MOD_INDEX * msg).astype(np.complex128)
    if variant == "DSB-SC":
        return (AM_MOD_INDEX * msg).astype(np.complex128)
    if variant == "SSB-WC":
        return (AM_CARRIER + AM_MOD_INDEX * _analytic(msg)).astype(np.complex128)
    if variant == "SSB-SC":
        return (AM_MOD_INDEX * _analytic(msg)).astype(np.complex128)
    raise ValueError("bad AM variant %r" % variant)


def _fm_signal(rng: np.random.Generator, n: int = N_SAMPLES) -> np.ndarray:
    msg = _bandlimited_message(rng, n)
    phase = rng.uniform(-np.pi, np.pi)
    out = np.empty(n, np.complex128)
    for k in range(n):
        phase += 2.0 * np.pi * FM_DEV_HZ * msg[k] / FS_BASE
        out[k] = np.exp(1j * phase)
    return out


def _gmsk_signal(rng: np.random.Generator, n: int = N_SAMPLES) -> np.ndarray:
    """Gaussian MSK: Gaussian-filtered NRZ (+-1) -> continuous phase.  BT=0.5,
    mod index 0.5 -> peak deviation symbol_rate/4 == MSK.  A 4-symbol warmup is
    generated and discarded so the Gaussian FIR is fully seeded."""
    sps = SPS
    tap_count = 2 * 4 * sps + 1
    sigma = max(sps / (2.0 * np.pi * GMSK_BT), 1.0)
    t = np.arange(tap_count) - (tap_count - 1) / 2.0
    g = np.exp(-t * t / (2.0 * sigma * sigma))
    g /= g.sum()
    warmup = 4 * sps
    n_sym = (n + warmup) // sps + 4
    sym = rng.integers(0, 2, n_sym).astype(np.float64) * 2.0 - 1.0
    center = (tap_count - 1) // 2
    total = n + warmup
    out = np.empty(total, np.complex128)
    phase = rng.uniform(-np.pi, np.pi)
    for i in range(total):
        shaped = 0.0
        for t_ in range(tap_count):
            k = i + center - t_
            if k >= 0:
                si = k // sps
                if si < n_sym:
                    shaped += g[t_] * sym[si]
        freq = shaped * GMSK_MOD_INDEX * (SYMBOL_RATE / 2.0)
        phase += 2.0 * np.pi * freq / FS_BASE
        out[i] = np.exp(1j * phase)
    return out[warmup:]


def _oqpsk_signal(rng: np.random.Generator, n: int = N_SAMPLES) -> np.ndarray:
    """Offset QPSK: Q branch delayed by half a symbol (sps/2 samples).  Each branch
    is an independent BPSK stream RRC-shaped, combined as (I + jQ)/sqrt(2)."""
    sps = SPS
    h = rrc_taps(sps)
    taps = h.size
    n_sym = n // sps + SPAN + 1
    i_sym = rng.integers(0, 2, n_sym).astype(np.float64) * 2.0 - 1.0
    q_sym = rng.integers(0, 2, n_sym).astype(np.float64) * 2.0 - 1.0
    total = n_sym * sps + taps + sps
    I = np.zeros(total, np.complex128)
    Q = np.zeros(total, np.complex128)
    for k in range(n_sym):
        I[k * sps:k * sps + taps] += i_sym[k] * h
        Q[k * sps + sps // 2:k * sps + sps // 2 + taps] += q_sym[k] * h
    x = (I + 1j * Q) / np.sqrt(2.0)
    start = (taps - 1) // 2 + (SPAN // 2) * sps
    return x[start:start + n]


# ---------------------------------------------------------------------------
# Per-source-class synthesis -> 1024-complex clean baseband (RMS 1.0).
# ---------------------------------------------------------------------------
def synthesize(source_class: int, rng: np.random.Generator,
               n: int = N_SAMPLES) -> np.ndarray:
    if source_class == 22:                           # GMSK
        return rms_normalize(_gmsk_signal(rng, n))
    if source_class in _CONSTELLATIONS:
        const = _CONSTELLATIONS[source_class]
        n_sym = n // SPS + SPAN
        sym = draw_symbols(rng, const, n_sym)
        return rms_normalize(pulse_shape(sym, n))
    if source_class == 17:                           # AM-SSB-WC
        return rms_normalize(_am_signal(rng, "SSB-WC"))
    if source_class == 18:                           # AM-SSB-SC
        return rms_normalize(_am_signal(rng, "SSB-SC"))
    if source_class == 19:                           # AM-DSB-WC
        return rms_normalize(_am_signal(rng, "DSB-WC"))
    if source_class == 20:                           # AM-DSB-SC
        return rms_normalize(_am_signal(rng, "DSB-SC"))
    if source_class == 21:                           # FM
        return rms_normalize(_fm_signal(rng, n))
    if source_class == 23:                           # OQPSK (raw) -- see const map
        return rms_normalize(_oqpsk_signal(rng, n))
    raise ValueError("no synthesis for source_class %d" % source_class)


def build_one_clean(source_class: int, sample_index: int) -> dict:
    """Synthesize one clean baseband and run the D2 reconstruction pipeline,
    returning the artifact dict mirroring build_route_d2_rf_artifacts.build_one."""
    rng = np.random.default_rng(file_seed(source_class, sample_index))
    x = synthesize(source_class, rng)
    # h5's D2 loader requires a stable 64-hex original identity.  Generated
    # clean data has no HDF5 source file, so define the identity as the canonical
    # little-endian complex64 bytes before D2 quantization.
    original_sha256 = sha256_bytes(np.ascontiguousarray(x, dtype="<c8").tobytes())
    r = A.reconstruct(x, "D2", GLOBAL_K, edge=EDGE, guard=GUARD)
    if r["clip_count"] > 0:
        raise RuntimeError("clip_count=%d at K=%.0f for source_class=%d: "
                           "fail-closed, no silent saturation"
                           % (r["clip_count"], GLOBAL_K, source_class))
    iq = r["iq"]
    return {
        "source_class": source_class,
        "original_sha256": original_sha256,
        "deployed_class": SOURCE_TO_DEPLOYED[source_class],
        "modulation": INDEX_TO_CLASS[source_class],
        "seed": file_seed(source_class, sample_index),
        "iq": iq,
        "recovered": A.recovered_tensor_1024(x, r["recovered"]),
        "dc_i": r["dc_i"],
        "dc_q": r["dc_q"],
        "ac_rms": r["ac_rms"],
        "rec_scale": r["rec_scale"],
        "tx_rms": float(np.sqrt(np.mean(iq.astype(np.float64) ** 2))),
        "tx_peak": float(np.max(np.abs(iq.astype(np.float64)))),
        "clip_count": r["clip_count"],
        "complex_count": iq.size // 2,
    }


# ---------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=None,
                    help="directory to write CI16 + tensors + manifests")
    ap.add_argument("--per-class", type=int, default=30,
                    help="samples per raw source class (default 30 -> 720)")
    ap.add_argument("--classes", default=None,
                    help="comma list of raw source class names to generate "
                         "(default: all 24); for smoke/testing only")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if not args.out_dir:
        ap.error("--out-dir is required unless --self-test")
    if args.per_class < 1:
        ap.error("--per-class must be >= 1")

    classes = list(range(N_SOURCE_CLASSES))
    if args.classes:
        want = [c.strip() for c in args.classes.split(",") if c.strip()]
        for c in want:
            if c not in SOURCE_CLASS_INDEX:
                ap.error("unknown class %r; allowed %s"
                         % (c, sorted(SOURCE_CLASS_INDEX)))
        classes = [SOURCE_CLASS_INDEX[c] for c in want]

    os.makedirs(args.out_dir, exist_ok=True)
    manifest_rows = []
    clean_rows = []
    n_files = 0

    # Order deterministically: source_class ascending, then sample_index ascending.
    for sc in classes:
        for i in range(args.per_class):
            art = build_one_clean(sc, i)
            out_idx = n_files
            qname = "clean_d2_2p56m_%06d.ci16" % out_idx
            rname = "clean_tensor_d2_%06d.f32" % out_idx
            qpath = os.path.join(args.out_dir, qname)
            rpath = os.path.join(args.out_dir, rname)
            art["iq"].tofile(qpath)
            art["recovered"].tofile(rpath)
            q_sha = sha256_file(qpath)
            r_sha = sha256_file(rpath)

            # 24-col route_d2_rf_manifest.tsv (load_d2_sidecar-compatible).
            manifest_rows.append([
                str(out_idx),                 # 0  sample_index
                str(out_idx),                 # 1  source_index (stable unique key)
                str(sc),                      # 2  raw24_class
                str(art["deployed_class"]),   # 3  deployed23_class
                art["modulation"],            # 4  modulation
                "nan",                        # 5  snr_db (clean = noise-free)
                "holdout",                    # 6  split_role
                "%.0f" % GLOBAL_K,            # 7  global_K
                "%.9g" % art["dc_i"],         # 8  original_dc_i
                "%.9g" % art["dc_q"],         # 9  original_dc_q
                "%.9g" % art["ac_rms"],       # 10 ac_rms
                "%.9g" % art["rec_scale"],    # 11 rec_scale
                str(art["complex_count"]),    # 12 complex_count
                str(SAMPLE_RATE_HZ),          # 13 sample_rate
                "%.6f" % art["tx_rms"],       # 14 tx_rms
                "%.6f" % art["tx_peak"],      # 15 tx_peak
                str(art["clip_count"]),       # 16 clip_count
                EDGE,                         # 17 edge_policy
                str(GUARD),                   # 18 guard
                art["original_sha256"],        # 19 canonical generated source SHA
                q_sha,                        # 20 quantized_sha256 (the ci16 TX)
                r_sha,                        # 21 recovered_tensor_sha256
                qname,                        # 22 quantized_file
                rname,                        # 23 recovered_tensor_file
            ])

            # 11-col clean manifest (fix10-prep §9 projection).
            clean_rows.append([
                str(out_idx),                 # source_index
                qname,                        # file_name
                art["modulation"],            # modulation
                str(sc),                      # source_class
                str(art["deployed_class"]),   # deployed_class
                str(art["complex_count"]),    # complex_samples
                str(SAMPLE_RATE_HZ),          # sample_rate
                "%.6f" % art["tx_rms"],       # component_rms
                q_sha,                        # sha256
                str(art["seed"]),             # seed
                "holdout",                    # split_role
            ])
            n_files += 1

    with open(os.path.join(args.out_dir, "route_d2_rf_manifest.tsv"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(MANIFEST_HEADER) + "\n")
        for mr in manifest_rows:
            fh.write("\t".join(mr) + "\n")

    with open(os.path.join(args.out_dir, "clean_manifest.tsv"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(CLEAN_MANIFEST_HEADER) + "\n")
        for cr in clean_rows:
            fh.write("\t".join(cr) + "\n")

    with open(os.path.join(args.out_dir, "clean_build.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump({
            "base_seed": BASE_SEED,
            "global_K": GLOBAL_K,
            "edge_policy": EDGE,
            "guard": GUARD,
            "sample_rate_hz": SAMPLE_RATE_HZ,
            "baseband_fs_hz": FS_BASE,
            "sps": SPS,
            "symbol_rate_hz": SYMBOL_RATE,
            "rolloff": ROLLOFF,
            "span_symbols": SPAN,
            "per_class": args.per_class,
            "num_files": n_files,
            "source_classes": [INDEX_TO_CLASS[c] for c in classes],
            "source_to_deployed": SOURCE_TO_DEPLOYED,
            "deployed_names": DEPLOYED_NAMES,
            "am_msg_cutoff_hz": AM_MSG_CUTOFF_HZ,
            "am_mod_index": AM_MOD_INDEX,
            "am_carrier": AM_CARRIER,
            "fm_dev_hz": FM_DEV_HZ,
            "gmsk_bt": GMSK_BT,
            "gmsk_mod_index": GMSK_MOD_INDEX,
            "ook_on": float(OOK_ON),
        }, fh, indent=2)

    print("GEN_GENERATED_CLEAN_23 files=%d per_class=%d classes=%d K=%.0f result=PASS"
          % (n_files, args.per_class, len(classes), GLOBAL_K))
    print("wrote %d artifacts + route_d2_rf_manifest.tsv + clean_manifest.tsv "
          "to %s" % (n_files, args.out_dir))
    return 0


# ---------------------------------------------------------------------------
# Self-test.
# ---------------------------------------------------------------------------
def self_test() -> int:
    npass = 0

    # 1. splitmix64/file_seed deterministic.
    if file_seed(3, 0) == file_seed(3, 0) and file_seed(3, 0) != file_seed(3, 1):
        npass += 1
        print("  OK  file_seed deterministic + sample-distinct")
    else:
        print("  BAD file_seed")

    # 2. constellations unit power.
    for sc, const in _CONSTELLATIONS.items():
        p = float(np.mean(np.abs(const) ** 2))
        if abs(p - 1.0) > 1e-9:
            print("  BAD constellation %d power %.12f" % (sc, p))
            return 1
    npass += 1
    print("  OK  all constellations unit average power")

    # 3. synthesis -> 1024 complex, RMS 1.0, deterministic.
    for sc in range(N_SOURCE_CLASSES):
        rng1 = np.random.default_rng(file_seed(sc, 0))
        rng2 = np.random.default_rng(file_seed(sc, 0))
        x1 = synthesize(sc, rng1)
        x2 = synthesize(sc, rng2)
        if (x1.size != N_SAMPLES or x2.size != N_SAMPLES
                or not np.array_equal(x1, x2)
                or abs(float(np.sqrt(np.mean(np.abs(x1) ** 2))) - 1.0) > 1e-6):
            print("  BAD synthesize class %d (size/rms/determinism)" % sc)
            return 1
    npass += 1
    print("  OK  all 24 classes synthesize 1024 cx RMS=1.0 deterministically")

    # 4. GMSK and OQPSK are distinct implementations.  GMSK is continuous
    # phase/constant-envelope; OQPSK is the half-symbol-offset shaped signal.
    gmsk = synthesize(22, np.random.default_rng(file_seed(22, 0)))
    oqpsk = synthesize(23, np.random.default_rng(file_seed(23, 0)))
    if (float(np.std(np.abs(gmsk))) < 1e-10
            and not np.array_equal(gmsk, oqpsk)):
        npass += 1
        print("  OK  raw24 class 22=GMSK and class 23=OQPSK are distinct")
    else:
        print("  BAD GMSK/OQPSK synthesis contract")

    # 5. D2 roundtrip is near-lossless for a clean 4ASK (AC+DC restored).
    rng = np.random.default_rng(file_seed(1, 0))
    x = synthesize(1, rng)
    r = A.reconstruct(x, "D2", GLOBAL_K, edge=EDGE, guard=GUARD)
    rec = A.recovered_tensor_1024(x, r["recovered"])
    recx = rec[:N_SAMPLES] + 1j * rec[N_SAMPLES:]
    nmse = float(np.sum(np.abs(x - recx) ** 2)) / float(np.sum(np.abs(x) ** 2))
    if nmse < 1e-2 and r["clip_count"] == 0:
        npass += 1
        print("  OK  D2 roundtrip near-lossless (nmse=%.3e)" % nmse)
    else:
        print("  BAD D2 roundtrip nmse=%.3e clip=%d" % (nmse, r["clip_count"]))

    # 6. 24->23 AM merge (both AM-SSB sources -> deployed 17).
    if (SOURCE_TO_DEPLOYED[17] == 17 and SOURCE_TO_DEPLOYED[18] == 17
            and DEPLOYED_NAMES[17] == "AM-SSB" and len(DEPLOYED_NAMES) == 23):
        npass += 1
        print("  OK  24->23 AM merge (17,18 -> deployed 17 AM-SSB)")
    else:
        print("  BAD 24->23 AM merge")

    # 7. byte-identical two-run generation on a small subset (2 classes x 2).
    import tempfile
    import shutil
    tmp1 = tempfile.mkdtemp(prefix="clean23_a_")
    tmp2 = tempfile.mkdtemp(prefix="clean23_b_")
    try:
        # Minimal inline generation (self-test only; mirrors main()).
        def _gen(out_dir):
            rows = []
            n = 0
            for sc in (1, 17):
                for i in range(2):
                    art = build_one_clean(sc, i)
                    qname = "clean_d2_2p56m_%06d.ci16" % n
                    rname = "clean_tensor_d2_%06d.f32" % n
                    art["iq"].tofile(os.path.join(out_dir, qname))
                    art["recovered"].tofile(os.path.join(out_dir, rname))
                    rows.append((qname, sha256_file(os.path.join(out_dir, qname)),
                                 rname, sha256_file(os.path.join(out_dir, rname))))
                    n += 1
            return rows
        ra = _gen(tmp1)
        rb = _gen(tmp2)
        if ra == rb and len(ra) == 4:
            npass += 1
            print("  OK  two-run generation byte-identical (4 files)")
        else:
            print("  BAD two-run generation not identical")
        # sizes
        if (os.path.getsize(os.path.join(tmp1, ra[0][0])) == 215040
                and os.path.getsize(os.path.join(tmp1, ra[0][2])) == 2 * N_SAMPLES * 4):
            npass += 1
            print("  OK  artifact sizes (ci16=215040 B, tensor=8192 B)")
        else:
            print("  BAD artifact sizes")
    finally:
        shutil.rmtree(tmp1, ignore_errors=True)
        shutil.rmtree(tmp2, ignore_errors=True)

    print("self-test: %d/8 correct" % npass)
    return 0 if npass == 8 else 1


if __name__ == "__main__":
    sys.exit(main())
