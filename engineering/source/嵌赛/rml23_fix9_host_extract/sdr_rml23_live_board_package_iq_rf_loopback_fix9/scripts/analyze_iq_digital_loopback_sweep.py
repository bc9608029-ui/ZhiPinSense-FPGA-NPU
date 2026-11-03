#!/usr/bin/env python3
"""analyze_iq_digital_loopback_sweep.py -- Stage H-E / Route E fix4 analyzer.

Reads the board's fix4 amplitude-sweep producer log
(board_gate9_full_chain_rml23.cpp, --phase=iq-digital-loopback-sweep) and
INDEPENDENTLY re-derives the root cause of the ~ -24 dB digital-loopback
amplitude loss from the SAME dual-domain discriminator the board uses:

  count_gain_db      = 20 log10(rx_count_rms / tx_count_rms)   (raw 16-bit container)
  normalized_gain_db = 20 log10((rx_count/2^(rx_bits-1)) / (tx_count/2^(tx_bits-1)))

The fix4 discriminator (classify_root_cause in iq_digital_loopback_sweep.hpp),
re-derived here in the SAME A->G order and thresholds (3 dB / 0.9):

  A  any captured level rx_libiio_diverged          -> LIBIIO_CONVERT_SEMANTICS
  B  no usable signal                               -> NOT_PROVEN
  C  reported decode inconsistent with the raw container (logical gain != count
     gain, or corr destroyed) AND a non-reported shift recovers BOTH shape (corr)
     and scale (logical gain == count gain)         -> FORMAT_MISALIGNMENT
  D  reported-format corr still below 0.9           -> NOT_PROVEN
  E  normalized ~0 dB: count matches the bit width  -> COUNT_DOMAIN_SCALE
     (same width + count ~0 -> UNITY)
  F  normalized << 0 dB                             -> FIXED_ATTENUATION
  G  otherwise                                      -> NOT_PROVEN

The analyzer re-reports the board's own token and cross-checks it against the
re-derived token (root_cause_match).  It NEVER promotes
DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN to PROVEN and never issues an accuracy
PASS/FAIL: the sweep is a DIAGNOSTIC instrument; fidelity (PRESERVES_IQ /
DISTORTS_IQ) is only established by --phase=iq-digital-loopback.

Inputs:
  --log LOG        board sweep stdout (repeatable, or a directory of *.log).
  --json PATH      write the full machine-readable record here.
  --selfcheck      run the built-in synthetic self-checks and exit.

stdlib only.  Run isolated:  python -I analyze_iq_digital_loopback_sweep.py ...
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

GAIN_PRESERVED_DB = 3.0
CORR_THRESHOLD = 0.9
QUANT_FLOOR_COUNTS = 2.0
VALID_LEVEL_MIN_TARGET = 64.0

ROOT_CAUSE_TOKENS = (
    "DIGITAL_LOOPBACK_COUNT_DOMAIN_SCALE",
    "DIGITAL_LOOPBACK_FIXED_ATTENUATION",
    "DIGITAL_LOOPBACK_FORMAT_MISALIGNMENT",
    "DIGITAL_LOOPBACK_LIBIIO_CONVERT_SEMANTICS",
    "DIGITAL_LOOPBACK_UNITY",
    "DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN",
)

_FORMAT_RE = re.compile(
    r"^IQ_DIGITAL_LOOPBACK_SWEEP_FORMAT dir=(tx|rx) "
    r"(\d+)b/(\d+)b shift\+(\d+) .* roundtrip_identity=(\d+)$")
_SIGNCHECK_RE = re.compile(
    r"^IQ_DIGITAL_LOOPBACK_SWEEP_SIGNCHECK fully_defined_ok=(\d+) "
    r"sign_extend_ok=(\d+) shift4_ok=(\d+) ok=(\d+)$")
_LEVEL_RE = re.compile(r"^IQ_DIGITAL_LOOPBACK_SWEEP_LEVEL ")
_SHIFT_SCAN_RE = re.compile(r"^IQ_DIGITAL_LOOPBACK_SWEEP_SHIFT_SCAN ")
_SHIFT_GROUP_RE = re.compile(
    r"shift=(-?\d+) count_gain_db=(\S+) normalized_gain_db=(\S+) "
    r"logical_gain_db=(\S+) corr=(\S+) clip_rate=(\S+)")
_SAMPLE_RE = re.compile(
    r"^IQ_DIGITAL_LOOPBACK_SWEEP_SAMPLE kind=\S+ target_rms=\S+ idx=(\d+) "
    r"tx_logical=(-?\d+) tx_raw=0x([0-9A-Fa-f]+) rx_raw=0x([0-9A-Fa-f]+) "
    r"rx_libiio=(-?\d+) rx_host_mirror=(-?\d+) rx_force_signed=(-?\d+)$")
_ROOT_CAUSE_RE = re.compile(
    r"^IQ_DIGITAL_LOOPBACK_SWEEP_ROOT_CAUSE token=(\S+) reason=(.*?) "
    r"components=(.*)$")
_SHIFT_CORR_RE = re.compile(
    r"^IQ_DIGITAL_LOOPBACK_SWEEP_SHIFT_CORRECTION shift=(-?\d+) gain_db=(\S+) "
    r"corr=(\S+) ok=(\d+)$")
_SCALE_RE = re.compile(
    r"^IQ_DIGITAL_LOOPBACK_SWEEP_SCALE_SELECTION (?:scale=(\S+) "
    r"expected_rx_rms=(\S+) reason=(.*)|ok=(\d+) reason=(.*))$")
_RECOMMEND_RE = re.compile(
    r"^IQ_DIGITAL_LOOPBACK_SWEEP_RECOMMENDATION action=(\S+)(?: (.*))?$")


def parse_kv(line: str) -> dict:
    d = {}
    for tok in line.split():
        if "=" in tok:
            k, _, v = tok.partition("=")
            d[k] = v
    return d


def to_int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def to_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def read_logs(log_args) -> list:
    lines = []
    for a in log_args:
        if os.path.isdir(a):
            for name in sorted(os.listdir(a)):
                if name.endswith(".log") or name.endswith(".txt"):
                    with open(os.path.join(a, name), "r", encoding="utf-8",
                              errors="replace") as f:
                        lines.extend(f.read().splitlines())
        else:
            with open(a, "r", encoding="utf-8", errors="replace") as f:
                lines.extend(f.read().splitlines())
    return lines


def median(values):
    if not values:
        return 0.0
    v = sorted(values)
    n = len(v)
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def norm_bits(bits):
    return 16 if (bits == 0 or bits > 16) else bits


def _expected_count_gain_db(tx_bits, rx_bits):
    return -20.0 * math.log10(2.0 ** (tx_bits - rx_bits))


def rederive_root_cause(levels, tx_bits, rx_bits, rx_shift):
    """Independent re-derivation of classify_root_cause() in
    board_package/iq_digital_loopback_sweep.hpp (same A->G order + thresholds)."""
    # A: libiio RX convert divergence (any captured level).
    for L in levels:
        if L.get("capture_ok") and L.get("rx_libiio_diverged"):
            return ("DIGITAL_LOOPBACK_LIBIIO_CONVERT_SEMANTICS",
                    "libiio RX convert output diverges from the host mirror of "
                    "the reported RX data format")

    # B: capture failed / RX all-zero / no usable signal.
    any_raw = any(L.get("capture_ok") for L in levels)
    any_signal = any(L.get("rx_count_rms", 0.0) >= QUANT_FLOOR_COUNTS for L in levels)
    if not any_raw or not any_signal:
        return ("DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN",
                "capture failed / RX all-zero / insufficient valid levels")

    # C: format misalignment -- a non-reported shift recovers BOTH shape and scale.
    for L in levels:
        if not L.get("capture_ok"):
            continue
        scan = L.get("shift_scan", [])
        if not scan:
            continue
        rep_clip = 0.0
        for e in scan:
            if e.get("shift") == rx_shift:
                rep_clip = e.get("clip_rate", 0.0)
        reported_inconsistent = (
            abs(L.get("gain_db", 0.0) - L.get("count_gain_db", 0.0))
            > GAIN_PRESERVED_DB or L.get("corr", 0.0) < CORR_THRESHOLD)
        if not reported_inconsistent:
            continue
        for e in scan:
            if e.get("shift") == rx_shift:
                continue
            recovers_shape = e.get("corr", 0.0) >= CORR_THRESHOLD
            recovers_scale = (
                abs(e.get("logical_gain_db", 0.0) - L.get("count_gain_db", 0.0))
                <= GAIN_PRESERVED_DB)
            no_clip = e.get("clip_rate", 0.0) <= rep_clip + 1e-6
            if recovers_shape and recovers_scale and no_clip:
                return ("DIGITAL_LOOPBACK_FORMAT_MISALIGNMENT",
                        "shift %d recovers both shape (corr %.3f) and scale "
                        "(logical gain %.2f dB == count gain %.2f dB) while the "
                        "reported shift %d decodes a logical gain %.2f dB"
                        % (e["shift"], e["corr"], e["logical_gain_db"],
                           L["count_gain_db"], rx_shift, L["gain_db"]))

    # Valid-level selection: high-amplitude band only, no clip, above the floor.
    norm_gain, count_gain, logical_gain, corr = [], [], [], []
    for L in levels:
        if not L.get("capture_ok"):
            continue
        if L.get("target_rms", 0.0) < VALID_LEVEL_MIN_TARGET:
            continue
        if L.get("rx_clip", 0) or L.get("tx_clip", 0) or L.get("rx_raw_clip", 0):
            continue
        if L.get("rx_count_rms", 0.0) < QUANT_FLOOR_COUNTS:
            continue
        norm_gain.append(L.get("normalized_gain_db", 0.0))
        count_gain.append(L.get("count_gain_db", 0.0))
        logical_gain.append(L.get("gain_db", 0.0))
        corr.append(L.get("corr", 0.0))

    # D: too few valid levels, or reported-format corr still below the threshold.
    if len(norm_gain) < 2:
        return ("DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN",
                "too few clip-free valid high-amplitude levels")
    ng, cg, lg, mc = median(norm_gain), median(count_gain), \
        median(logical_gain), median(corr)
    if mc < CORR_THRESHOLD:
        return ("DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN",
                "median corr %.3f < %.2f: gain alone is not fidelity (count "
                "%.2f dB, normalized %.2f dB)" % (mc, CORR_THRESHOLD, cg, ng))

    tb, rb = norm_bits(tx_bits), norm_bits(rx_bits)

    # The reported decode must be consistent with the raw container.
    if abs(lg - cg) > GAIN_PRESERVED_DB:
        return ("DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN",
                "reported decode inconsistent with the raw container: logical "
                "gain %.2f dB vs count gain %.2f dB, and no shift recovered "
                "consistency" % (lg, cg))

    # E: normalized ~0 dB.
    if abs(ng) <= GAIN_PRESERVED_DB:
        if tb != rb:
            expected = _expected_count_gain_db(tb, rb)
            if abs(cg - expected) <= GAIN_PRESERVED_DB:
                return ("DIGITAL_LOOPBACK_COUNT_DOMAIN_SCALE",
                        "count gain %.2f dB matches the TX%d/RX%d full-scale "
                        "difference (%.2f dB); normalized gain %.2f dB ~ 0"
                        % (cg, tb, rb, expected, ng))
        else:
            if abs(cg) <= GAIN_PRESERVED_DB:
                return ("DIGITAL_LOOPBACK_UNITY",
                        "count gain %.2f dB and normalized gain %.2f dB ~ 0: "
                        "loopback is unity at these levels" % (cg, ng))

    # F: normalized significantly < 0 dB.
    if ng < -GAIN_PRESERVED_DB:
        return ("DIGITAL_LOOPBACK_FIXED_ATTENUATION",
                "normalized gain %.2f dB remains below 0 after the TX%d/RX%d "
                "full-scale normalization; corr %.3f, no clip: a real "
                "level-independent attenuation" % (ng, tb, rb, mc))

    # G: otherwise.
    return ("DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN",
            "unexplained: count gain %.2f dB, normalized gain %.2f dB, corr %.3f"
            % (cg, ng, mc))


def analyze(log_args):
    rec = {
        "tx_format": None,
        "rx_format": None,
        "tx_bits": None,
        "rx_bits": None,
        "rx_shift": None,
        "signcheck": None,
        "levels": [],
        "board_root_cause": None,
        "rederived_root_cause": None,
        "root_cause_match": None,
        "shift_correction": None,
        "scale_selection": None,
        "recommendations": [],
        "gate_result": None,
        "loopback_capability": "DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN",
    }

    cur_level = None
    for line in read_logs(log_args):
        if not line.strip():
            continue

        m = _FORMAT_RE.match(line)
        if m:
            fmt = {"dir": m.group(1), "length_bits": to_int(m.group(2)),
                   "bits": to_int(m.group(3)), "shift": to_int(m.group(4)),
                   "roundtrip_identity": m.group(5) == "1"}
            rec[m.group(1) + "_format"] = fmt
            if m.group(1) == "tx":
                rec["tx_bits"] = fmt["bits"]
            else:
                rec["rx_bits"] = fmt["bits"]
                rec["rx_shift"] = fmt["shift"]
            continue

        m = _SIGNCHECK_RE.match(line)
        if m:
            rec["signcheck"] = {
                "fully_defined_ok": m.group(1) == "1",
                "sign_extend_ok": m.group(2) == "1",
                "shift4_ok": m.group(3) == "1",
                "ok": m.group(4) == "1",
            }
            continue

        if _LEVEL_RE.match(line):
            d = parse_kv(line)
            cur_level = {
                "kind": d.get("kind"),
                "target_rms": to_float(d.get("target_rms")),
                "tx_count_rms": to_float(d.get("tx_count_rms")),
                "rx_count_rms": to_float(d.get("rx_count_rms")),
                "count_gain_db": to_float(d.get("count_gain_db")),
                "tx_normalized_rms": to_float(d.get("tx_normalized_rms")),
                "rx_normalized_rms": to_float(d.get("rx_normalized_rms")),
                "normalized_gain_db": to_float(d.get("normalized_gain_db")),
                "gain_db": to_float(d.get("gain_db")),
                "corr": to_float(d.get("corr")),
                "tx_clip": to_int(d.get("tx_clip")),
                "rx_clip": to_int(d.get("rx_clip")),
                "rx_raw_clip": to_int(d.get("rx_raw_clip")),
                "rx_libiio_diverged": d.get("rx_libiio_diverged") == "1",
                "capture_ok": d.get("capture_ok") == "1",
                "shift_scan": [],
                "samples": [],
            }
            rec["levels"].append(cur_level)
            continue

        if _SHIFT_SCAN_RE.match(line):
            scan = []
            for g in _SHIFT_GROUP_RE.finditer(line):
                scan.append({
                    "shift": to_int(g.group(1)),
                    "count_gain_db": to_float(g.group(2)),
                    "normalized_gain_db": to_float(g.group(3)),
                    "logical_gain_db": to_float(g.group(4)),
                    "corr": to_float(g.group(5)),
                    "clip_rate": to_float(g.group(6)),
                })
            if cur_level is not None:
                cur_level["shift_scan"] = scan
            continue

        m = _SAMPLE_RE.match(line)
        if m:
            if cur_level is not None:
                cur_level["samples"].append({
                    "idx": to_int(m.group(1)),
                    "tx_logical": to_int(m.group(2)),
                    "tx_raw": int(m.group(3), 16),
                    "rx_raw": int(m.group(4), 16),
                    "rx_libiio": to_int(m.group(5)),
                    "rx_host_mirror": to_int(m.group(6)),
                    "rx_force_signed": to_int(m.group(7)),
                })
            continue

        m = _ROOT_CAUSE_RE.match(line)
        if m:
            rec["board_root_cause"] = {
                "token": m.group(1),
                "reason": m.group(2),
                "components": [c for c in m.group(3).split(",") if c],
            }
            continue

        m = _SHIFT_CORR_RE.match(line)
        if m:
            rec["shift_correction"] = {
                "shift": to_int(m.group(1)),
                "gain_db": to_float(m.group(2)),
                "corr": to_float(m.group(3)),
                "ok": m.group(4) == "1",
            }
            continue

        m = _SCALE_RE.match(line)
        if m:
            if m.group(1) is not None:
                rec["scale_selection"] = {
                    "ok": True,
                    "scale": to_float(m.group(1)),
                    "expected_rx_rms": to_float(m.group(2)),
                    "reason": m.group(3),
                }
            else:
                rec["scale_selection"] = {
                    "ok": m.group(4) == "1",
                    "reason": m.group(5),
                }
            continue

        m = _RECOMMEND_RE.match(line)
        if m:
            rec["recommendations"].append({
                "action": m.group(1),
                "semantics": m.group(2) or None,
            })
            continue

        if line.startswith("GATE_RESULT"):
            d = parse_kv(line)
            rec["gate_result"] = {"gate": d.get("gate"), "result": d.get("result"),
                                  "detail": d}
            continue

    # Independent re-derivation + cross-check.
    tb = rec["tx_bits"] if rec["tx_bits"] is not None else 16
    rb = rec["rx_bits"] if rec["rx_bits"] is not None else 12
    rs = rec["rx_shift"] if rec["rx_shift"] is not None else 0
    token, reason = rederive_root_cause(rec["levels"], tb, rb, rs)
    rec["rederived_root_cause"] = {"token": token, "reason": reason}
    if rec["board_root_cause"] is not None:
        rec["root_cause_match"] = (rec["board_root_cause"]["token"] == token)

    return rec


def render(rec):
    lines = []
    a = lines.append
    a("=" * 72)
    a("Route E fix4 -- digital-loopback amplitude-sweep (root-cause diagnosis)")
    a("loopback_capability=%s" % rec["loopback_capability"])
    a("=" * 72)

    a("")
    a("[1] DATA FORMAT (req 1) + SIGNCHECK (fix4 corrected convert mirror)")
    for d, key in (("tx", "tx_format"), ("rx", "rx_format")):
        f = rec[key]
        if f:
            a("    dir=%-2s %db/%db shift+%d roundtrip_identity=%s"
              % (d, f["length_bits"], f["bits"], f["shift"],
                 f["roundtrip_identity"]))
        else:
            a("    dir=%-2s <not reported>" % d)
    sc = rec["signcheck"]
    if sc:
        a("    SIGNCHECK fully_defined_ok=%s sign_extend_ok=%s shift4_ok=%s ok=%s"
          % (sc["fully_defined_ok"], sc["sign_extend_ok"], sc["shift4_ok"], sc["ok"]))

    a("")
    a("[2] AMPLITUDE SWEEP (req 2/3: count-domain vs normalized-domain)")
    a("    %-6s %-8s %-10s %-10s %-9s %-9s %-9s %-7s %-7s %-5s %-6s %s"
      % ("kind", "target", "tx_count", "rx_count", "count_g", "norm_g",
         "gain_db", "corr", "clip", "div", "cap_ok", "note"))
    for L in rec["levels"]:
        note = ""
        if not L["capture_ok"]:
            note = "capture-fail"
        elif L["target_rms"] < VALID_LEVEL_MIN_TARGET:
            note = "low-amp (boundary only)"
        elif L["rx_clip"] or L["tx_clip"] or L["rx_raw_clip"]:
            note = "clip (excluded)"
        elif L["rx_count_rms"] < QUANT_FLOOR_COUNTS:
            note = "sub-floor (excluded)"
        else:
            note = "valid"
        a("    %-6s %-8.1f %-10.3f %-10.3f %-9.3f %-9.3f %-9.3f %-7.4f "
          "%-7d %-6d %-6d %s"
          % (L["kind"], L["target_rms"], L["tx_count_rms"], L["rx_count_rms"],
             L["count_gain_db"], L["normalized_gain_db"], L["gain_db"],
             L["corr"], (L["rx_clip"] + L["tx_clip"] + L["rx_raw_clip"]),
             1 if L["rx_libiio_diverged"] else 0,
             1 if L["capture_ok"] else 0, note))

    a("")
    a("[3] SHIFT SCAN (fix4: logical gain at each bit position, shift 0..4)")
    shown = False
    for L in rec["levels"]:
        if not L.get("shift_scan"):
            continue
        shown = True
        a("    kind=%-6s target_rms=%.1f" % (L["kind"], L["target_rms"]))
        for e in L["shift_scan"]:
            a("        shift=%d count=%.2f norm=%.2f logical=%.2f corr=%.4f "
              "clip=%.4f"
              % (e["shift"], e["count_gain_db"], e["normalized_gain_db"],
                 e["logical_gain_db"], e["corr"], e["clip_rate"]))
    if not shown:
        a("    <no shift-scan lines>")

    a("")
    a("[4] ROOT CAUSE (fix4 A->G, 3 dB / 0.9)")
    if rec["board_root_cause"]:
        a("    board      token=%s" % rec["board_root_cause"]["token"])
        a("    board      reason=%s" % rec["board_root_cause"]["reason"])
        a("    board      components=%s"
          % ",".join(rec["board_root_cause"]["components"]))
    else:
        a("    board      token=<none>")
    a("    re-derived token=%s" % rec["rederived_root_cause"]["token"])
    a("    re-derived reason=%s" % rec["rederived_root_cause"]["reason"])
    a("    root_cause_match=%s"
      % (rec["root_cause_match"] if rec["root_cause_match"] is not None else "n/a"))

    if rec["shift_correction"]:
        sc = rec["shift_correction"]
        a("    format correction (req 5): shift=%d gain_db=%.3f corr=%.6f ok=%s"
          % (sc["shift"], sc["gain_db"], sc["corr"], sc["ok"]))
    ss = rec["scale_selection"]
    if ss:
        if ss.get("ok"):
            a("    test-fixture scale (req 6/7): scale=%.6f expected_rx_rms=%.3f"
              % (ss["scale"], ss["expected_rx_rms"]))
        else:
            a("    test-fixture scale: ok=0 reason=%s" % ss["reason"])
    for r in rec["recommendations"]:
        if r["semantics"]:
            a("    recommendation: %s  (%s)" % (r["action"], r["semantics"]))
        else:
            a("    recommendation: %s" % r["action"])

    a("")
    a("[5] GATE (diagnostic gate: PASS = a root cause was diagnosed AND device "
      "params restored)")
    if rec["gate_result"]:
        a("    gate=%s result=%s" % (rec["gate_result"]["gate"],
                                     rec["gate_result"]["result"]))
    else:
        a("    <no GATE_RESULT line>")

    a("")
    a("DISTINCTION (fix4): count-domain gain is the RAW 16-bit container ratio; "
      "normalized gain removes the TX/RX signed full scale (TX16 fs=32768, RX12 "
      "fs=2048).  COUNT_DOMAIN_SCALE = normalized ~0 dB with a count gain that "
      "matches the bit width (NOT a hardware attenuation).  DIGITAL_LOOPBACK_"
      "CAPABILITY_NOT_PROVEN is never promoted here; fidelity (PRESERVES_IQ / "
      "DISTORTS_IQ) is only established by --phase=iq-digital-loopback.")
    return "\n".join(lines)


# ---- built-in synthetic self-checks -----------------------------------------

def _lvl(target_rms, count_gain, normalized_gain, gain_db, corr,
         tx_clip=0, rx_clip=0, rx_raw_clip=0, rx_libiio_diverged=False,
         rx_count_rms=100.0, shift_scan=None):
    return {
        "kind": "tone",
        "target_rms": target_rms,
        "tx_count_rms": 100.0,
        "rx_count_rms": rx_count_rms,
        "count_gain_db": count_gain,
        "tx_normalized_rms": 0.0,
        "rx_normalized_rms": 0.0,
        "normalized_gain_db": normalized_gain,
        "gain_db": gain_db,
        "corr": corr,
        "tx_clip": tx_clip,
        "rx_clip": rx_clip,
        "rx_raw_clip": rx_raw_clip,
        "rx_libiio_diverged": rx_libiio_diverged,
        "capture_ok": True,
        "shift_scan": shift_scan or [],
    }


def _scan_entry(shift, logical_gain, corr, clip_rate=0.0):
    return {"shift": shift, "count_gain_db": 0.0, "normalized_gain_db": 0.0,
            "logical_gain_db": logical_gain, "corr": corr, "clip_rate": clip_rate}


def run_selfcheck():
    checks = []
    # 1. TX16/RX12 count-domain scale: count ~-24 dB, normalized ~0 dB.
    checks.append((
        "count-domain scale (TX16/RX12)",
        rederive_root_cause(
            [_lvl(128.0, -24.08, 0.0, -24.08, 0.99),
             _lvl(256.0, -24.08, 0.0, -24.08, 0.99)], 16, 12, 0)[0],
        "DIGITAL_LOOPBACK_COUNT_DOMAIN_SCALE"))
    # 2. Real fixed attenuation (TX12/RX12): normalized ~-20 dB.
    checks.append((
        "fixed attenuation (TX12/RX12)",
        rederive_root_cause(
            [_lvl(128.0, -20.0, -20.0, -20.0, 0.99),
             _lvl(256.0, -20.0, -20.0, -20.0, 0.99)], 12, 12, 0)[0],
        "DIGITAL_LOOPBACK_FIXED_ATTENUATION"))
    # 3. Shift error: reported shift 4 decodes a -24 dB logical gain, shift 0
    #    recovers both shape and scale.
    scan = [_scan_entry(0, 0.0, 0.99), _scan_entry(1, -6.02, 0.99),
            _scan_entry(2, -12.04, 0.99), _scan_entry(3, -18.06, 0.99),
            _scan_entry(4, -24.08, 0.99)]
    checks.append((
        "format misalignment (shift scan)",
        rederive_root_cause(
            [_lvl(128.0, 0.0, 0.0, -24.08, 0.99, shift_scan=scan),
             _lvl(256.0, 0.0, 0.0, -24.08, 0.99, shift_scan=scan)], 12, 12, 4)[0],
        "DIGITAL_LOOPBACK_FORMAT_MISALIGNMENT"))
    # 4. libiio/host mirror divergence.
    checks.append((
        "libiio convert semantics",
        rederive_root_cause(
            [_lvl(128.0, -24.08, 0.0, -24.08, 0.99, rx_libiio_diverged=True)],
            16, 12, 0)[0],
        "DIGITAL_LOOPBACK_LIBIIO_CONVERT_SEMANTICS"))
    # 5. Correct gain but corr below the fidelity threshold.
    checks.append((
        "corr insufficient",
        rederive_root_cause(
            [_lvl(128.0, -24.08, 0.0, -24.08, 0.5),
             _lvl(256.0, -24.08, 0.0, -24.08, 0.5)], 16, 12, 0)[0],
        "DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN"))
    # 6. Clipped levels excluded -> no valid level -> NOT_PROVEN.
    checks.append((
        "clipping",
        rederive_root_cause(
            [_lvl(128.0, -24.08, 0.0, -24.08, 0.99, rx_clip=100),
             _lvl(256.0, -24.08, 0.0, -24.08, 0.99, rx_clip=100)], 16, 12, 0)[0],
        "DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN"))

    ok = True
    print("analyzer self-checks:")
    for name, got, want in checks:
        good = got == want
        ok = ok and good
        print("  %-40s %-45s -> %s" %
              (name, got, "OK" if good else "FAIL (want %s)" % want))
    print("  selfcheck %s" % ("PASS" if ok else "FAIL"))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", action="append", default=[],
                    help="board sweep stdout (repeatable, or a directory)")
    ap.add_argument("--json", default=None)
    ap.add_argument("--selfcheck", action="store_true",
                    help="run the built-in synthetic self-checks and exit")
    args = ap.parse_args()

    if args.selfcheck:
        sys.exit(0 if run_selfcheck() else 1)

    if not args.log:
        ap.error("--log is required (the board's --phase=iq-digital-loopback-sweep "
                 "stdout)")

    rec = analyze(args.log)
    print(render(rec))

    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rec, f, indent=2, sort_keys=True)
        print("wrote %s" % args.json)


if __name__ == "__main__":
    main()
