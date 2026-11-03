#!/usr/bin/env python3
"""fix4_common.py -- shared constants + frozen-input access for Fix4.

Fix4 = M29-RML24-FIX10CLASS24-INDEPENDENT-RX-ADAPTIVE-TRACKER-FIX4.  Pure offline.
Reuses Fix3-R1 (read-only) as the frozen recovery substrate: fix3_common (identity
+ fail-closed I/O) and fix3_recovery (byte-exact fix2 chain).
"""
from __future__ import annotations

import sys
from pathlib import Path

_FIX3_SCRIPTS = r"F:\嵌赛\fix10class24_independent_rx_payload_fidelity_fix3_work\scripts"
if _FIX3_SCRIPTS not in sys.path:
    sys.path.insert(0, _FIX3_SCRIPTS)

import fix3_common as FC  # noqa: E402
import fix3_recovery as R  # noqa: E402

# Frozen model identity (Fix4 taskbook §2).
FROZEN_MODEL_JSON_SHA256 = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA256 = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

# Frozen capture directories (read-only).
CAPTURE_LATEST = Path(r"F:\嵌赛\board_capture\rml24_fix2_dual_1773374951_244")
CAPTURE_OLD = Path(r"F:\嵌赛\board_capture\rml24_independent_v2_dual_1773374217_210")

# Digital v2 baseline (no-RF replay; 23/24, known error AM-DSB-SC->256QAM).
REPLAY_OUT = Path(r"F:\嵌赛\fix10class24_waveform_correct_v2_work\replay_out")

# Model dir candidates (auto-located; SHA verified fail-closed).
MODEL_DIR_CANDIDATES = [
    r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work\sdr_rml24_fix10class24_original_radioml_npu_ab1\model_rml24_bf16",
]
ICRAFT_RUN = Path(r"D:\icraft\bin\icraft-run.exe")

# Public-reference burst layout (aligned coordinates), re-exported from fix3_recovery.
SETTLE_START, SETTLE_END = R.SETTLE_START, R.SETTLE_END        # 1024..2048 silence
TRAIN_START, TRAIN_END = R.TRAIN_START, R.TRAIN_END            # 2048..3072 16QAM
PAYLOAD_START, PAYLOAD_END = R.PAYLOAD_START, R.PAYLOAD_END    # 3072..56832 unknown
GUARD_START, GUARD_END = R.GUARD_START, R.GUARD_END            # 56832..58880 silence
TAIL_START, TAIL_END = R.TAIL_START, R.TAIL_END                # 58880..59904 ZC tail
K_TOTAL = R.K_TOTAL
GATE = FC.GATE_THRESHOLD                                       # 0.100


def locate_model_dir() -> Path:
    """Auto-locate + SHA-verify the frozen model (fail-closed)."""
    for d in MODEL_DIR_CANDIDATES:
        d = Path(d)
        j = d / "rml24_adamrv11_bf16.json"
        r = d / "rml24_adamrv11_bf16.raw"
        if j.is_file() and r.is_file():
            if (FC.sha256_file(j) == FROZEN_MODEL_JSON_SHA256
                    and FC.sha256_file(r) == FROZEN_MODEL_RAW_SHA256):
                return d
    raise RuntimeError("frozen model not found / SHA mismatch (fail-closed)")


def public_dc_observations(aligned) -> list[tuple[float, complex]]:
    """DC observations at the 4 public-reference block centers (aligned coords).

    Each is the block mean: settle/train/guard/tail content is ~zero-mean (16QAM
    symmetric / ZC chirp), so the block mean approximates the DC at that time.
    Reads ONLY public regions -- never the unknown payload.
    """
    def center(a, b):
        return (a + b) / 2.0
    return [
        (center(SETTLE_START, SETTLE_END), complex(aligned[SETTLE_START:SETTLE_END].mean())),
        (center(TRAIN_START, TRAIN_END), complex(aligned[TRAIN_START:TRAIN_END].mean())),
        (center(GUARD_START, GUARD_END), complex(aligned[GUARD_START:GUARD_END].mean())),
        (center(TAIL_START, TAIL_END), complex(aligned[TAIL_START:TAIL_END].mean())),
    ]
