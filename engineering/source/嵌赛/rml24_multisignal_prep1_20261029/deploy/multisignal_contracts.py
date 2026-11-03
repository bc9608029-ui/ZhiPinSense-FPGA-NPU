"""Frozen multi-signal scan contracts (C-line, offline only).

Every value here is either copied verbatim from the frozen public contract
(``F:/嵌赛/SHARED_CONTRACT_PARALLEL_20261029.md``), the frozen FPGA smart-scan
contract, or is an explicitly-labelled offline assumption that must be
re-verified on the board before any RF claim.  Nothing in this file emits RF,
touches hardware, writes flash, or trains a model.

Frequency unit: Hz, integer, ``*_hz`` field names only (contract sec. 3).
"""

from __future__ import annotations

# --- contract sec. 3 (frozen, 2026-10-29 revision) ----------------------------
SAMPLE_RATE_HZ: int = 2_560_000
FFT_LENGTH: int = 1024
BIN_HZ: int = SAMPLE_RATE_HZ // FFT_LENGTH          # 2500 Hz per FFT bin (physical fact)

# --- scan geometry (from main-chain scan_runtime.py ScanConfig) ---------------
USABLE_BAND_FRACTION: float = 0.90
# 0.9 * fs = 2_304_000 is the main-chain EXISTING scan span / upper limit
# (ScanConfig.validate's value), NOT fs, and NOT a bin-alignment requirement.
# Contract sec. 3 (revised): the tuning step is NOT inherently a multiple of
# 2500 Hz; do not impose that restriction unless the real receiver/controller
# actually has an alignment premise (to be verified and recorded).  Spectral
# stitching therefore uses real integer-Hz coordinates.
MAX_SCAN_STEP_HZ: int = int(USABLE_BAND_FRACTION * SAMPLE_RATE_HZ)  # 2_304_000
DEFAULT_SCAN_STEP_HZ: int = 1_000_000
MIN_SCAN_STEP_HZ: int = 1

# --- public frame protocol (frozen) -------------------------------------------
# detect_public_training uses a 2x1024 public training block; recover_frame
# tensorizes 8 windows of 1024 payload samples.  Frame = 2048 + 8192 = 10240.
TRAIN_REPEAT: int = 1024
PUBLIC_TRAIN_SAMPLES: int = 2 * TRAIN_REPEAT        # 2048
PAYLOAD_WINDOWS: int = 8
PAYLOAD_SAMPLES: int = PAYLOAD_WINDOWS * 1024       # 8192
FRAME_SAMPLES: int = PUBLIC_TRAIN_SAMPLES + PAYLOAD_SAMPLES  # 10240
MIN_PUBLIC_SCORE: float = 0.10

# --- dwell / observation (offline budget; board-measured value pending) -------
CAPTURE_SAMPLES: int = 65_536
FLUSH_CAPTURES: int = 2
DWELL_BUDGET_SECONDS: float = 0.25   # upper bound: 3 captures + LO settle

# --- multi-target separation/detection: OFFLINE TEST TARGETS -------------------
# These numbers are offline-derived TEST TARGETS (from the Hann-window PSD
# model), NOT frozen commitments.  They must be re-verified on the board against
# the REAL public-frame occupied bandwidth, guard band and detection algorithm
# before any separation/dynamic-range claim is made.  Contract sec. 8 still
# scores any miss as a fixed error, so an unverified target never inflates a
# detection rate.
# Hann-window main lobe is ~4 bins (10 kHz).  Two equal-power tones are expected
# separable only at >= 5 bins; closer spacing is expected to merge.
RESOLVABLE_SEPARATION_HZ: int = 5 * BIN_HZ          # 12_500 (test target)
MERGE_RADIUS_HZ: int = int(2.5 * BIN_HZ)            # 6_250 (< resolvable gap)
# Hann first sidelobe ~ -31.5 dB.  A neighbour weaker than this below an
# adjacent strong tone is expected NOT to be separable.
NEAR_NEIGHBOR_DYNAMIC_RANGE_DB: float = 25.0        # test target
MIN_TARGET_BW_HZ: int = BIN_HZ                      # 1 bin
MAX_TARGET_BW_HZ: int = int(0.45 * SAMPLE_RATE_HZ)  # 1_152_000 usable half-band

# --- detection thresholds (offline-derived, configurable, board-verify) -------
# White-Gaussian-noise PSD on 1024 bins is chi-square(2): its expected maximum
# sits ~10 dB above the median, so median + 14 dB keeps the false-alarm rate
# negligible.  Board verification pending.
NOISE_FLOOR_QUANTILE: float = 0.50                   # median
PEAK_THRESHOLD_DB: float = 14.0                      # above median noise floor
OCCUPIED_BW_DB: float = 20.0                         # occupied band = within 20 dB of peak
RESOLVABLE_SEPARATION_BINS: int = RESOLVABLE_SEPARATION_HZ // BIN_HZ  # 5

# --- power measurement contract (target record field ``power_valid``) ----------
# The field ``power_valid`` carries a NUMERIC power measurement, not a bare
# flag: the peak PSD power of the detected occupied span expressed in dB ABOVE
# the dwell's adaptive median noise floor (a relative scale).  It is NOT dBm
# and NOT dBFS -- no absolute metrological contract exists offline, so dBm must
# never be reported from this field.
POWER_UNIT: str = "dB above adaptive median noise floor (relative scale, NOT dBm)"
POWER_SOURCE: str = ("detection PSD peak power minus the dwell's adaptive median "
                     "noise floor (prominence of the selected peak)")
POWER_VALID_MIN_DB: float = float(PEAK_THRESHOLD_DB)  # a detection requires >= this
POWER_VALID_MAX_DB: float = 80.0                      # psd_db normalizes peak to 80 dB
POWER_INVALID_DB: float = float("nan")                # sentinel: unmeasured/invalid

# --- aging (contract sec. 7) --------------------------------------------------
AGING_CYCLES_DEFAULT: int = 3

# --- backend / status enums (contract sec. 1 and sec. 7) ----------------------
BACKENDS: tuple[str, ...] = ("software", "fpga", "auto")
TARGET_STATUSES: tuple[str, ...] = ("new", "tracking", "missing", "expired")

# --- TX synthesis (task 4, offline assumptions to be board-verified) ----------
TX_SAMPLE_RATE_HZ: int = 2_560_000          # assumption: TX baseband == RX rate
TX_FULL_SCALE: int = 30_000                 # int16 DAC full scale (matches UI clip)
TX_USABLE_HALF_BAND_HZ: int = int(0.45 * TX_SAMPLE_RATE_HZ)  # 1_152_000
TX_GUARD_BAND_HZ: int = RESOLVABLE_SEPARATION_HZ            # offline stand-in >= resolvable test target
TX_HEADROOM_DB: float = 12.0                # reference DAC backoff for clip audit


def validate_scan_step_hz(step_hz: int) -> None:
    """Contract sec. 3 (revised): step is a positive integer Hz <= the scan span.

    No 2500 Hz multiple restriction is imposed by default; the step is only
    required to be a positive integer and not exceed the main-chain existing
    span/upper limit MAX_SCAN_STEP_HZ (2_304_000 = 0.9 * fs).  Real receivers
    may add an alignment premise, but that must be verified and recorded, not
    assumed here.
    """
    if not isinstance(step_hz, int) or isinstance(step_hz, bool):
        raise ValueError("scan step must be an integer")
    if step_hz <= 0:
        raise ValueError("scan step must be positive")
    if step_hz > MAX_SCAN_STEP_HZ:
        raise ValueError(f"scan step exceeds {MAX_SCAN_STEP_HZ} Hz")
