"""fix10clean2a Phase 2 — clean RadioML2018.01A-domain signal synthesis.

Answers: does the frozen PyTorch model recognise *clean* (noise-free, no random
channel impairment) IQ constructed in the local RadioML2018.01A domain?

Domain contract (measured in Phase 1 + raw-frame probes, see the Phase 1 profile
and Phase 4 gate):
  * 1024 samples/frame, 200 kHz native sample rate, sps=8 -> 128 symbols/frame.
  * linear digital modulations: windowed-sinc lowpass pulse (fc=0.059, Hann,
    65 taps) — the measured RadioML2018.01A pulse, NOT RRC.
  * per-class RMS is NOT uniform; every class is scaled to its measured target
    RMS (TARGET_RMS below).
  * OOK/4ASK/8ASK are UNIPOLAR (strong DC: |mean| ~= 1.1/1.4/1.6) — NOT centred.
  * OOK/4ASK/8ASK/BPSK are REAL baseband signals; the data's Q~=0.5 energy comes
    from a random per-frame channel phase.  The clean form is a DETERMINISTIC
    constant 45 deg rotation (energy split evenly over I/Q, matching the model's
    training distribution) — no random phase, no CFO.
  * FM is analytic (Q == Hilbert(I)), constant envelope, carrier at +6250 Hz
    (Fs/32), frequency sensitivity ~514 Hz (inst-freq std).
  * AM-DSB is real-carrier DSB: (1 + m*sawtooth[n]) * cos(2pi*fc*t) * e^{j pi/4}
    (sawtooth = one cycle/frame; WC m=0.10, SC m=0.15).  AM-SSB is broadband
    (multi-tone audio), near zero mean (|mean|~0.08).

Deterministic: every generator consumes a per-frame seed and derives all its
randomness (symbols / bits / audio tones) from it via a local PCG64.

RED LINE (mandatory): source index 22 == GMSK and 23 == OQPSK, exactly.
"""

from __future__ import annotations

import numpy as np

SAMPLE_LENGTH = 1024
SAMPLE_RATE_HZ = 200_000.0
SPS = 8
N_SYMBOLS = SAMPLE_LENGTH // SPS            # 128
WSINC_FC = 0.059                            # pulse cutoff (fraction of Fs)
WSINC_NTAPS = 65                            # pulse length
ANALOG_CARRIER_HZ = SAMPLE_RATE_HZ / 32.0   # 6250 Hz (measured FM/DSB carrier)
CLEAN_PHASE = np.pi / 4.0                   # deterministic 45 deg for real mods

LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)

# Per-class target RMS, measured at SNR>=20 in Phase 1 (clean == noise-free).
TARGET_RMS = {
    "OOK": 1.4714, "4ASK": 1.7525, "8ASK": 1.9116,
    "BPSK": 1.0, "QPSK": 1.0, "8PSK": 1.0, "16PSK": 1.0, "32PSK": 1.0,
    "16APSK": 1.0, "32APSK": 1.0, "64APSK": 1.0, "128APSK": 1.0,
    "16QAM": 1.0, "32QAM": 1.0, "64QAM": 1.0, "128QAM": 1.0, "256QAM": 1.0,
    "AM-SSB-WC": 11.7392, "AM-SSB-SC": 7.8328,
    "AM-DSB-WC": 1.0, "AM-DSB-SC": 1.0, "FM": 1.0,
    "GMSK": 1.0, "OQPSK": 1.0,
}

# Real-valued (single-axis) modulations get the clean 45 deg rotation.
REAL_MODS = {"OOK", "4ASK", "8ASK", "BPSK"}


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


# ---------------------------------------------------------------------------
# pulse shaping
# ---------------------------------------------------------------------------
def _sinc(x: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(x) < 1e-12, 1.0, np.sin(np.pi * x) / (np.pi * x))


def wsinc_taps(fc: float = WSINC_FC, ntaps: int = WSINC_NTAPS) -> np.ndarray:
    """Windowed-sinc lowpass pulse (unit energy) — the measured RadioML pulse."""
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = 2.0 * fc * _sinc(2.0 * fc * n)
    h = h * np.hanning(ntaps)
    return h / np.sqrt(np.sum(h ** 2))


_H = wsinc_taps()


def _pulse_shape(symbols: np.ndarray, sps: int, h: np.ndarray) -> np.ndarray:
    up = np.zeros(len(symbols) * sps, dtype=np.complex128)
    up[::sps] = symbols
    x = np.convolve(up, h)
    delay = (len(h) - 1) // 2
    return x[delay:delay + len(symbols) * sps]


def _scale_rms(x: np.ndarray, target: float) -> np.ndarray:
    rms = np.sqrt(np.mean(np.abs(x) ** 2))
    return x * (target / (rms + 1e-12))


def _frac_shift(x: np.ndarray, d: float) -> np.ndarray:
    """Fractional-sample shift of x by d (d<0 advances) via linear interpolation."""
    n = len(x)
    idx = np.arange(n) + d
    i0 = np.floor(idx).astype(int)
    i1 = i0 + 1
    fr = idx - i0
    i0 = np.clip(i0, 0, n - 1)
    i1 = np.clip(i1, 0, n - 1)
    return x[i0] * (1.0 - fr) + x[i1] * fr


def _hilbert(a: np.ndarray) -> np.ndarray:
    """Discrete Hilbert transform (single-sideband analytic companion)."""
    A = np.fft.fft(a)
    h = np.zeros_like(A)
    n = len(a)
    h[0] = 1.0
    if n % 2 == 0:
        h[1:n // 2] = 2.0
        h[n // 2] = 1.0
    else:
        h[1:(n + 1) // 2] = 2.0
    return np.fft.ifft(A * h).real


# ---------------------------------------------------------------------------
# constellations
# ---------------------------------------------------------------------------
_PSK_ORDER = {"BPSK": 2, "QPSK": 4}


def _psk(m: int) -> np.ndarray:
    return np.exp(1j * 2 * np.pi * np.arange(m) / m)


def _qam(m: int) -> np.ndarray:
    if m in (16, 64, 256):
        n = int(np.sqrt(m))
        pts = np.array([a + 1j * b for a in np.arange(-(n - 1), n, 2) for b in np.arange(-(n - 1), n, 2)])
    elif m == 32:
        pts = np.array(_cross_qam_32())
    elif m == 128:
        pts = np.array(_cross_qam_128())
    else:
        raise ValueError(m)
    return pts / np.sqrt(np.mean(np.abs(pts) ** 2))


def _cross_qam_32() -> list[complex]:
    # 6x6 odd-integer grid, 4 corners removed -> 32 points.
    pts: list[complex] = []
    for a in range(-5, 6, 2):
        for b in range(-5, 6, 2):
            if not (abs(a) == 5 and abs(b) == 5):
                pts.append(a + 1j * b)
    return pts


def _cross_qam_128() -> list[complex]:
    # 12x12 odd-integer grid, 4x4 corner blocks removed -> 128 points.
    pts: list[complex] = []
    for a in range(-11, 12, 2):
        for b in range(-11, 12, 2):
            if not (abs(a) >= 9 and abs(b) >= 9):
                pts.append(a + 1j * b)
    return pts


def _ask(m: int) -> np.ndarray:
    # UNIPOLAR on-off levels {0..m-1} (DC kept — measured |mean| is large).
    levels = np.arange(m, dtype=np.float64)
    return levels / np.sqrt(np.mean(levels ** 2))


def _apsk(m: int) -> np.ndarray:
    if m == 16:
        rings = [(4, 1.0), (12, 2.57)]
    elif m == 32:
        rings = [(4, 1.0), (12, 2.84), (16, 5.27)]
    elif m == 64:
        rings = [(4, 1.0), (12, 2.2), (20, 3.6), (28, 5.6)]
    elif m == 128:
        # DVB-S2X 128APSK: 6 rings 16+16+16+16+16+48, radii ratio R/R1 =
        # (1, 1.715, 2.118, 2.681, 2.75, 3.819).
        rings = [(16, 1.0), (16, 1.715), (16, 2.118), (16, 2.681), (16, 2.75), (48, 3.819)]
    else:
        raise ValueError(m)
    pts: list[complex] = []
    for count, radius in rings:
        off = np.random.default_rng(0).uniform(0, 2 * np.pi)
        for k in range(count):
            pts.append(radius * np.exp(1j * (2 * np.pi * k / count + off)))
    pts = np.array(pts)
    return pts / np.sqrt(np.mean(np.abs(pts) ** 2))


def _constellation(name: str) -> np.ndarray:
    if name == "OOK":
        return _ask(2)
    if name.endswith("APSK"):
        return _apsk(int(name[:-4]))
    if name.endswith("PSK"):
        return _psk(_PSK_ORDER.get(name) or int(name[:-3]))
    if name.endswith("QAM"):
        return _qam(int(name[:-3]))
    if name.endswith("ASK"):
        return _ask(int(name[:-3]))
    raise ValueError(name)


# ---------------------------------------------------------------------------
# digital generators
# ---------------------------------------------------------------------------
def _linear_digital(name: str, rng: np.random.Generator) -> np.ndarray:
    const = _constellation(name)
    symbols = const[rng.integers(0, len(const), size=N_SYMBOLS)]
    x = _pulse_shape(symbols, SPS, _H)
    if name in REAL_MODS:
        x = x * np.exp(1j * CLEAN_PHASE)     # deterministic clean phase -> Q~=0.5
    return _scale_rms(x, TARGET_RMS[name])


def _gmsk(rng: np.random.Generator, bt: float = 0.3) -> np.ndarray:
    bits = 2.0 * rng.integers(0, 2, size=N_SYMBOLS) - 1.0
    span = 4
    k = np.arange(-span * SPS / 2, span * SPS / 2 + 1)
    t = k / SPS
    sigma = np.sqrt(np.log(2)) / (2 * np.pi * bt)
    g = np.exp(-t ** 2 / (2 * sigma ** 2))
    g = g / g.sum()
    up = np.zeros(N_SYMBOLS * SPS)
    up[::SPS] = bits
    freq = np.convolve(up, g)[:N_SYMBOLS * SPS]
    phase = np.cumsum(freq) * (np.pi / 2.0)
    x = np.exp(1j * phase)
    return _scale_rms(x, TARGET_RMS["GMSK"])


def _oqpsk(rng: np.random.Generator) -> np.ndarray:
    # RadioML OQPSK quirk: Q is the SAME bit stream as I, advanced by 11.5
    # samples (fractional), NOT a delayed independent bit stream.  Measured
    # offset D=-11.5 (Q[n]=I[n+D]) reproduces the data (recall ~0.97).
    bits = 2.0 * rng.integers(0, 2, size=N_SYMBOLS) - 1.0
    i = _pulse_shape(bits, SPS, _H)
    q = _frac_shift(i, -11.5)
    return _scale_rms(i + 1j * q, TARGET_RMS["OQPSK"])


# ---------------------------------------------------------------------------
# analog generators
# ---------------------------------------------------------------------------
def _audio(rng: np.random.Generator, n: int, fs: float, fmax: float = 3000.0) -> np.ndarray:
    # multi-tone audio in [200, fmax] Hz (matches measured discrete spectral
    # peaks and moderate analog PAPR), unit RMS, deterministic per seed.
    ntone = int(rng.integers(3, 5))
    freqs = rng.uniform(200.0, fmax, size=ntone)
    amps = rng.uniform(0.5, 1.0, size=ntone)
    phases = rng.uniform(0, 2 * np.pi, size=ntone)
    tt = np.arange(n) / fs
    a = np.zeros(n)
    for f, A, p in zip(freqs, amps, phases):
        a += A * np.sin(2 * np.pi * f * tt + p)
    return a / (np.sqrt(np.mean(a ** 2)) + 1e-12)


def _sawtooth(rng: np.random.Generator) -> np.ndarray:
    """Real sawtooth, one cycle per frame (period = SAMPLE_LENGTH), phase-random."""
    phase = rng.uniform(0.0, 1.0)
    n = np.arange(SAMPLE_LENGTH)
    return 2.0 * ((n / SAMPLE_LENGTH + phase) % 1.0) - 1.0


def _am_dsb(rng: np.random.Generator, carrier: bool) -> np.ndarray:
    # Real-carrier DSB: x = (1 + m*s[n]) * cos(2pi*fc*t) * e^{j pi/4}, where s is
    # a REAL sawtooth at Fs/N (one cycle/frame, harmonics ~1/n).  WC/SC differ by
    # modulation index (m=0.10 / 0.15), NOT carrier presence.  The carrier is a
    # real cos at +/-6250 Hz (an analytic e^{j2pi fc t} carrier is misread as
    # FM/32APSK).
    s = _sawtooth(rng)
    tt = np.arange(SAMPLE_LENGTH) / SAMPLE_RATE_HZ
    m = 0.10 if carrier else 0.15
    x = (1.0 + m * s) * np.cos(2 * np.pi * ANALOG_CARRIER_HZ * tt) * np.exp(1j * CLEAN_PHASE)
    return _scale_rms(x, TARGET_RMS["AM-DSB-WC" if carrier else "AM-DSB-SC"])


def _am_ssb(rng: np.random.Generator, carrier: bool) -> np.ndarray:
    # DC carrier + tiny upper-sideband: x = (1 + m*(a + j*Hilbert(a))) * e^{j pi/4}.
    # The carrier is a DC (zero-frequency) tone, NOT a complex carrier at +6250
    # (that form is misread as 8PSK).  WC has a stronger carrier (smaller m),
    # SC a relatively stronger sideband (larger m).
    a = _audio(rng, SAMPLE_LENGTH, SAMPLE_RATE_HZ)
    z = a + 1j * _hilbert(a)                 # analytic audio -> USB sideband
    m = 0.06 if carrier else 0.09
    x = (1.0 + m * z) * np.exp(1j * CLEAN_PHASE)
    return _scale_rms(x, TARGET_RMS["AM-SSB-WC" if carrier else "AM-SSB-SC"])


def _fm(rng: np.random.Generator, freq_sens_hz: float = 514.0) -> np.ndarray:
    a = _audio(rng, SAMPLE_LENGTH, SAMPLE_RATE_HZ)
    tt = np.arange(SAMPLE_LENGTH) / SAMPLE_RATE_HZ
    # analytic FM: carrier at +6250 Hz, frequency sensitivity ~514 Hz (inst std).
    phase = 2 * np.pi * (ANALOG_CARRIER_HZ * tt + freq_sens_hz * np.cumsum(a) / SAMPLE_RATE_HZ)
    x = np.exp(1j * phase)
    return _scale_rms(x, TARGET_RMS["FM"])


# ---------------------------------------------------------------------------
# top-level dispatcher
# ---------------------------------------------------------------------------
def generate_class(name: str, seed: int) -> np.ndarray:
    """Return a clean complex-baseband frame (1024,) for one class."""
    if name not in LABEL_ORDER_24:
        raise ValueError(f"unknown class {name!r}")
    rng = _rng(seed)
    if name in ("OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
                "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM",
                "64QAM", "128QAM", "256QAM"):
        return _linear_digital(name, rng)
    if name == "GMSK":
        return _gmsk(rng)
    if name == "OQPSK":
        return _oqpsk(rng)
    if name == "FM":
        return _fm(rng)
    if name == "AM-DSB-WC":
        return _am_dsb(rng, carrier=True)
    if name == "AM-DSB-SC":
        return _am_dsb(rng, carrier=False)
    if name == "AM-SSB-WC":
        return _am_ssb(rng, carrier=True)
    if name == "AM-SSB-SC":
        return _am_ssb(rng, carrier=False)
    raise ValueError(name)
