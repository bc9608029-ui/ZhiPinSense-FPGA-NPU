#!/usr/bin/env python3
"""fix3_common.py -- shared constants + fail-closed I/O for the Fix3 audit.

Fix3 = M29-RML24-FIX10CLASS24-INDEPENDENT-RX-PAYLOAD-FIDELITY-FIX3.  Anomaly
under audit: 24 frames processed / 23 gated / 23 classified, only 1/24 correct,
19 predicted AM-SSB-SC (18) and 4 predicted AM-SSB-WC (17) -- a collapse to the
two SSB classes.  This module pins the frozen identities and the read-only
helpers every Fix3 script shares, so no script can silently re-define the model
or the label order.

Pure stdlib + numpy.  Offline (API machine) only; never touches the board / NPU
/ SDR / Flash.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Frozen identities (do NOT edit; these are the contractual constants).
# ---------------------------------------------------------------------------
FROZEN_MODEL_JSON_SHA256 = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA256 = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
NETWORK_NAME = "model_24class"
EXPECT_CLASS_COUNT = 24
EXPECT_FRAMES = 24

# RadioML2018.01A 24-class label order (0..23).  Matches the class_name column
# in board_independent_rx_results.tsv and rml24::kLabelOrder24 on the board.
LABELS = [
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
]

# AM-family classes of interest for the collapse analysis.
WC_CLASS, SC_CLASS = 17, 18

# Model input contract: float32 planar [I(1024), Q(1024)] = 2048 floats = 8192B.
TENSOR_FLOATS = 2048
TENSOR_BYTES = TENSOR_FLOATS * 4
FRAME_COMPLEX = 1024

# raw.i16 capture contract: 544768 bytes of interleaved int16 IQ.
RAW_I16_BYTES = 544768

# Recovery gate: training_residual_rel <= GATE_THRESHOLD.
GATE_THRESHOLD = 0.100

RESULTS_HEADER = [
    "source_index", "class_index", "class_name", "timing_offset", "coarse_cfo_hz",
    "fractional_timing", "cfo_preamble_legacy_hz", "a_real", "a_imag", "b_real",
    "b_imag", "training_residual", "training_residual_rel", "gated", "finite",
    "repeatable", "board_pred", "capture_ok", "no_sync", "rx_clipped",
    "raw_rx_sha256", "logits_sha256", "model_input_sha256",
]


def fail(msg: str) -> "None":
    print("FAIL: %s" % msg, file=sys.stderr)
    sys.exit(1)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        fail("file not found: %s" % path)
    return sha256_bytes(path.read_bytes())


def read_tsv(path: Path) -> tuple[list[str], list[dict]]:
    """Read a TSV, returning (header, rows).  Fail-closed on any malformed row."""
    if not path.is_file():
        fail("TSV not found: %s" % path)
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        fail("empty TSV: %s" % path)
    header = lines[0].rstrip("\n").split("\t")
    rows = []
    for lineno, ln in enumerate(lines[1:], start=2):
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        if len(f) != len(header):
            fail("TSV %s row %d has %d cols (want %d)" % (path, lineno, len(f), len(header)))
        rows.append(dict(zip(header, f)))
    return header, rows


def write_tsv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    lines = ["\t".join(header)]
    for r in rows:
        lines.append("\t".join(str(x) for x in r))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_results_tsv(path: Path) -> list[dict]:
    """Load board_independent_rx_results.tsv (21-col), fail-closed on schema."""
    header, rows = read_tsv(path)
    if header != RESULTS_HEADER:
        fail("results TSV header mismatch: got %d cols, want the 21-col schema"
             % len(header))
    if len(rows) != EXPECT_FRAMES:
        fail("results TSV has %d rows (want %d)" % (len(rows), EXPECT_FRAMES))
    out = []
    seen = set()
    for r in rows:
        sid = int(r["source_index"])
        if sid in seen:
            fail("duplicate source_index=%d in results TSV" % sid)
        seen.add(sid)
        out.append(r)
    return out


def parse_logits_tsv(path: Path) -> dict[str, list[float]]:
    """Parse an N.logits.tsv, returning {'pass1': [...24 floats], 'pass2': [...]}.

    A gate-rejected frame has empty pass rows ('pass1'/'pass2' with no value
    columns) -> both lists empty.  Fail-closed on any non-empty row that is not
    exactly 24 finite floats.  (read_tsv's strict equal-column check cannot be
    reused here because the empty-pass rows legitimately carry only the tag.)
    """
    if not path.is_file():
        fail("logits TSV not found: %s" % path)
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        fail("empty logits TSV: %s" % path)
    header = lines[0].rstrip("\n").split("\t")
    if header[0] != "pass" or len(header) != EXPECT_CLASS_COUNT + 1:
        fail("logits TSV %s header not 'pass logit_00..logit_23'" % path)
    for i in range(EXPECT_CLASS_COUNT):
        if header[i + 1] != "logit_%02d" % i:
            fail("logits TSV %s bad header col %d" % (path, i + 1))
    out: dict[str, list[float]] = {"pass1": [], "pass2": []}
    seen: set[str] = set()
    for lineno, ln in enumerate(lines[1:], start=2):
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        tag = f[0]
        if tag not in ("pass1", "pass2"):
            fail("logits TSV %s unexpected pass tag %r" % (path, tag))
        if tag in seen:
            fail("logits TSV %s duplicate pass tag %r" % (path, tag))
        seen.add(tag)
        if len(f) == 1:
            # empty pass (gate-rejected frame): no value columns
            continue
        if len(f) != EXPECT_CLASS_COUNT + 1:
            fail("logits TSV %s row %d has %d cols (want %d)"
                 % (path, lineno, len(f), EXPECT_CLASS_COUNT + 1))
        vals = []
        for s in f[1:]:
            try:
                vals.append(float(s))
            except ValueError:
                fail("logits TSV %s non-numeric value %r" % (path, s))
        out[tag] = vals
    return out


def dumps_json(obj: dict, path: Path) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
