#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_fix10class24_rx_frontend_sweep.py -- host-side FAIL-CLOSED checker for the
fix10class24-rxfrontend1 RX-bandwidth sweep.

The board sweep (scripts/run_fix10class24_rx_frontend_sweep.sh) writes, for every
bandwidth level x round, a directory

    /tmp/rml24_rxbw_<hz>_run<1..3>_<ts>/run.log

containing the board runner's full stdout.  This checker walks those directories,
parses EVERY key field (never a single GATE_RESULT token), re-derives the §八
per-round pass conditions, and selects the WIDEST RX bandwidth that passes 3/3
rounds.  Any missing / duplicate / non-finite / identity-mismatched field is a FAIL.

Exit codes: 0 = a candidate bandwidth was selected; 1 = no stable bandwidth
(NO_STABLE_RX_BANDWIDTH); 2 = usage / precondition error.

Pure stdlib; the parsing + judging logic is importable so the host tests can
exercise it directly without board logs on disk.
"""

import os
import re
import statistics
import sys

# ---- sweep contract (must match run_fix10class24_rx_frontend_sweep.sh) ----
BANDWIDTH_LEVELS_HZ = (18000000, 10000000, 5000000, 3000000)  # widest first
ROUNDS = 3
RX_GAIN_DB_REQUIRED = 35.0
TX_ATTEN_DB_REQUIRED = -40.0
GAIN_TOL_DB = 0.5
TX_ATTEN_TOL_DB = 0.05
PAYLOAD_RESIDUAL_MAX = 0.10
BPSK_INDEX = 1500
FOUR_ASK_INDEX = 500
ROUND_DIR_RE = re.compile(r"rml24_rxbw_(\d+)_run([123])_\d+$")


class CheckError(Exception):
    """A structural parse failure that makes a round/sweep undecidable (fail-closed)."""


def _tokenize(line):
    """Split one log line into key=value tokens.  Values carry no whitespace."""
    tokens = {}
    for tok in line.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            tokens[k] = v
    return tokens


def _f(tokens, key, where):
    """Fetch a required float token, or raise CheckError."""
    if key not in tokens:
        raise CheckError("%s missing field %s" % (where, key))
    try:
        return float(tokens[key])
    except ValueError:
        raise CheckError("%s non-numeric %s=%r" % (where, key, tokens[key]))


def _i(tokens, key, where):
    """Fetch a required int token, or raise CheckError."""
    if key not in tokens:
        raise CheckError("%s missing field %s" % (where, key))
    try:
        return int(tokens[key])
    except ValueError:
        raise CheckError("%s non-integer %s=%r" % (where, key, tokens[key]))


def _finite(value):
    try:
        return value == value and value not in (float("inf"), float("-inf"))
    except Exception:
        return False


class RoundLog:
    """Structured view of one round's board log."""

    def __init__(self):
        self.rx_frontend = None
        self.hello_ack = None
        self.two_sample = None
        self.samples = {}          # file name -> merged per-sample dict
        self.error_lines = []      # FIX10CLASS24_BF16_ERROR payloads


def parse_rx_frontend(line):
    return _tokenize(line)


def parse_hello_ack(line):
    return _tokenize(line)


def parse_two_sample_result(line):
    return _tokenize(line)


def parse_log_text(text):
    """Parse a full round log (str) into a RoundLog.  Raises CheckError on a
    structural problem (missing/duplicate singleton lines, missing sample lines)."""
    rl = RoundLog()
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line:
            continue
        if line.startswith("FIX10CLASS24_BF16_ERROR"):
            rl.error_lines.append(line)
            continue
        if line.startswith("FIX10CLASS24_BF16_RX_FRONTEND "):
            if rl.rx_frontend is not None:
                raise CheckError("duplicate RX_FRONTEND line")
            rl.rx_frontend = parse_rx_frontend(line)
            continue
        if line.startswith("FIX10CLASS24_BF16_HELLO_ACK "):
            if rl.hello_ack is not None:
                raise CheckError("duplicate HELLO_ACK line")
            rl.hello_ack = parse_hello_ack(line)
            continue
        if line.startswith("FIX10CLASS24_BF16_TWO_SAMPLE_RESULT "):
            if rl.two_sample is not None:
                raise CheckError("duplicate TWO_SAMPLE_RESULT line")
            rl.two_sample = parse_two_sample_result(line)
            continue
        # Per-sample identity line: FIX10CLASS24_BF16_FILE ... source_index= ...
        if line.startswith("FIX10CLASS24_BF16_FILE ") and "source_index=" in line:
            t = _tokenize(line)
            if "file" not in t:
                raise CheckError("FILE identity line missing file=")
            s = rl.samples.setdefault(t["file"], {})
            s["file"] = t["file"]
            s["source_index"] = _i(t, "source_index", "FILE")
            s["modulation"] = t.get("modulation", "")
            s["source_class"] = _i(t, "source_class", "FILE")
            continue
        if line.startswith("FIX10CLASS24_BF16_CFO "):
            t = _tokenize(line)
            if "file" not in t:
                raise CheckError("CFO line missing file=")
            s = rl.samples.setdefault(t["file"], {})
            s["file"] = t["file"]
            s["coarse_cfo_hz"] = _f(t, "coarse_cfo_hz", "CFO")
            s["fine_cfo_hz"] = _f(t, "fine_cfo_hz", "CFO")
            s["total_cfo_hz"] = _f(t, "total_cfo_hz", "CFO")
            s["fractional_timing_samples"] = _f(t, "fractional_timing_samples", "CFO")
            s["cfo_finite"] = _i(t, "cfo_finite", "CFO")
            s["cfo_in_range"] = _i(t, "cfo_in_range", "CFO")
            continue
        if line.startswith("FIX10CLASS24_BF16_RECOVERY "):
            t = _tokenize(line)
            if "file" not in t:
                raise CheckError("RECOVERY line missing file=")
            s = rl.samples.setdefault(t["file"], {})
            s["file"] = t["file"]
            s["computed"] = _i(t, "computed", "RECOVERY")
            s["valid"] = _i(t, "valid", "RECOVERY")
            s["gain_mag"] = _f(t, "gain_mag", "RECOVERY")
            s["payload_gain_mag"] = _f(t, "payload_gain_mag", "RECOVERY")
            s["payload_rms_gain_mag"] = _f(t, "payload_rms_gain_mag", "RECOVERY")
            s["training_corr"] = _f(t, "training_corr", "RECOVERY")
            s["training_residual"] = _f(t, "training_residual", "RECOVERY")
            s["payload_training_corr"] = _f(t, "payload_training_corr", "RECOVERY")
            s["payload_training_residual"] = _f(t, "payload_training_residual", "RECOVERY")
            s["rx_clipped"] = _i(t, "rx_clipped", "RECOVERY")
            s["fidelity"] = t.get("fidelity", "")
            continue
        if line.startswith("FIX10CLASS24_BF16_CLASSIFY "):
            t = _tokenize(line)
            if "file" not in t:
                raise CheckError("CLASSIFY line missing file=")
            s = rl.samples.setdefault(t["file"], {})
            s["file"] = t["file"]
            s["baseline_pred"] = _i(t, "baseline_pred", "CLASSIFY")
            s["rf_pred"] = _i(t, "rf_pred", "CLASSIFY")
            s["prediction_agreement"] = _i(t, "prediction_agreement", "CLASSIFY")
            s["label_correct"] = _i(t, "label_correct", "CLASSIFY")
            s["finite"] = _i(t, "finite", "CLASSIFY")
            continue
    # Fail-closed structural checks.
    if rl.rx_frontend is None:
        raise CheckError("missing RX_FRONTEND line")
    if rl.hello_ack is None:
        raise CheckError("missing HELLO_ACK line")
    if rl.two_sample is None:
        raise CheckError("missing TWO_SAMPLE_RESULT line")
    if len(rl.samples) != 2:
        raise CheckError("expected exactly 2 samples, got %d" % len(rl.samples))
    if any(s.get("source_index") is None for s in rl.samples.values()):
        raise CheckError("a sample is missing its source_index")
    return rl


def _sample_by_modulation(rl):
    by_mod = {}
    for s in rl.samples.values():
        m = s.get("modulation", "")
        if m in by_mod:
            raise CheckError("duplicate modulation %s" % m)
        by_mod[m] = s
    return by_mod


def judge_round(rl, expected_bandwidth_hz, expected_bpsk_index=BPSK_INDEX,
                expected_4ask_index=FOUR_ASK_INDEX, rx_gain_db=RX_GAIN_DB_REQUIRED,
                tx_atten_db=TX_ATTEN_DB_REQUIRED):
    """Apply every §八 per-round condition.  Returns (ok: bool, checks: list[str]).

    The conditions are evaluated independently and never short-circuit, so a single
    failing field does not hide the others.  GATE_RESULT=PASS is DERIVED: it is true
    only when every listed condition holds AND no infra error line appeared."""
    checks = []

    def cond(name, ok):
        checks.append("%s=%s" % (name, "PASS" if ok else "FAIL"))
        return ok

    ok = True
    # (a) no infra error line.
    ok = cond("no_error_line", len(rl.error_lines) == 0) and ok

    # (b) RX frontend write-then-readback.
    rf = rl.rx_frontend
    rx_bw_ok = _i(rf, "rx_bw_ok", "RX_FRONTEND") == 1
    rx_gain_ok = _i(rf, "rx_gain_ok", "RX_FRONTEND") == 1
    req_bw = _i(rf, "requested_rx_bw", "RX_FRONTEND")
    rb_bw = _i(rf, "rx_bw_readback", "RX_FRONTEND")
    req_gain = _f(rf, "requested_rx_gain", "RX_FRONTEND")
    rb_gain = _f(rf, "rx_gain_readback", "RX_FRONTEND")
    ok = cond("rx_bw_ok", rx_bw_ok) and ok
    ok = cond("rx_gain_ok", rx_gain_ok) and ok
    ok = cond("requested_rx_bw_matches_level", req_bw == expected_bandwidth_hz) and ok
    ok = cond("rx_bw_readback_consistent",
              rx_bw_ok and _bw_consistent(req_bw, rb_bw)) and ok
    ok = cond("requested_rx_gain_matches", abs(req_gain - rx_gain_db) < 1e-9) and ok
    ok = cond("rx_gain_readback_consistent",
              rx_gain_ok and abs(rb_gain - rx_gain_db) <= GAIN_TOL_DB) and ok

    # (c) TX attenuation must be the -40 dB safety ceiling.
    ack = rl.hello_ack
    tx_att = _f(ack, "tx_atten_db", "HELLO_ACK")
    ok = cond("tx_atten_is_ceiling", abs(tx_att - tx_atten_db) <= TX_ATTEN_TOL_DB) and ok

    # (d) sample identity: exactly BPSK + 4ASK with the expected source indices.
    by_mod = _sample_by_modulation(rl)
    ok = cond("bpsk_present", "BPSK" in by_mod) and ok
    ok = cond("4ask_present", "4ASK" in by_mod) and ok
    if "BPSK" in by_mod:
        ok = cond("bpsk_source_index",
                  by_mod["BPSK"].get("source_index") == expected_bpsk_index) and ok
    if "4ASK" in by_mod:
        ok = cond("4ask_source_index",
                  by_mod["4ASK"].get("source_index") == expected_4ask_index) and ok

    # (e) two-sample summary fields.
    ts = rl.two_sample
    holdout = 2
    scored = _i(ts, "scored", "TWO_SAMPLE_RESULT")
    rf_excluded = _i(ts, "rf_excluded", "TWO_SAMPLE_RESULT")
    nan_or_inf = _i(ts, "nan_or_inf", "TWO_SAMPLE_RESULT")
    cfo_finite = _i(ts, "cfo_finite", "TWO_SAMPLE_RESULT")
    cfo_in_range = _i(ts, "cfo_in_range", "TWO_SAMPLE_RESULT")
    tx_restore = _i(ts, "tx_restore_ok", "TWO_SAMPLE_RESULT")
    rx_restore = _i(ts, "rx_restore_ok", "TWO_SAMPLE_RESULT")
    neg = ts.get("negative_control", "")
    pa = _ratio(ts, "prediction_agreement", "TWO_SAMPLE_RESULT")
    lc = _ratio(ts, "label_correct", "TWO_SAMPLE_RESULT")
    rd = _ratio(ts, "repeat_deterministic", "TWO_SAMPLE_RESULT")
    tv = _ratio(ts, "training_estimate_valid", "TWO_SAMPLE_RESULT")
    ok = cond("scored==2", scored == holdout) and ok
    ok = cond("rf_excluded==0", rf_excluded == 0) and ok
    ok = cond("prediction_agreement==2/2", pa == (holdout, holdout)) and ok
    ok = cond("label_correct==2/2", lc == (holdout, holdout)) and ok
    ok = cond("repeat_deterministic==2/2", rd == (holdout, holdout)) and ok
    ok = cond("training_estimate_valid==2/2", tv == (holdout, holdout)) and ok
    ok = cond("negative_control==PASS", neg == "PASS") and ok
    ok = cond("cfo_finite==1", cfo_finite == 1) and ok
    ok = cond("cfo_in_range==1", cfo_in_range == 1) and ok
    ok = cond("tx_restore_ok==1", tx_restore == 1) and ok
    ok = cond("rx_restore_ok==1", rx_restore == 1) and ok
    ok = cond("nan_or_inf==0", nan_or_inf == 0) and ok

    # (f) per-sample recovery + classification checks.
    for name, s in sorted(by_mod.items()):
        resid = s.get("payload_training_residual")
        clipped = s.get("rx_clipped")
        finite = s.get("finite")
        pred_ok = s.get("prediction_agreement")
        label_ok = s.get("label_correct")
        ok = cond("%s_residual<=%.3f" % (name, PAYLOAD_RESIDUAL_MAX),
                  resid is not None and _finite(resid) and resid <= PAYLOAD_RESIDUAL_MAX) and ok
        ok = cond("%s_rx_clipped==0" % name, clipped == 0) and ok
        ok = cond("%s_finite==1" % name, finite == 1) and ok
        ok = cond("%s_prediction_agreement==1" % name, pred_ok == 1) and ok
        ok = cond("%s_label_correct==1" % name, label_ok == 1) and ok

    return ok, checks


def _ratio(tokens, key, where):
    if key not in tokens:
        raise CheckError("%s missing field %s" % (where, key))
    m = re.fullmatch(r"(\d+)/(\d+)", tokens[key])
    if not m:
        raise CheckError("%s malformed ratio %s=%r" % (where, key, tokens[key]))
    return (int(m.group(1)), int(m.group(2)))


def _bw_consistent(requested, readback):
    """Mirror rf_fix::rf_readback_close(..., 1000, 0.05)."""
    if requested == 0:
        return readback == 0
    d = abs(readback - requested)
    rel = int(round(abs(requested) * 0.05))
    tol = max(1000, rel)
    return d <= tol


def _rounds_for_bandwidth(sweep_dir, bandwidth_hz):
    """Return {round_no: dir_path} for a bandwidth level, in the sweep dir."""
    found = {}
    for name in os.listdir(sweep_dir):
        m = ROUND_DIR_RE.match(name)
        if not m:
            continue
        if int(m.group(1)) != bandwidth_hz:
            continue
        r = int(m.group(2))
        if r in found:
            raise CheckError("duplicate round %d for bandwidth %d" % (r, bandwidth_hz))
        found[r] = os.path.join(sweep_dir, name)
    return found


def analyze_bandwidth(sweep_dir, bandwidth_hz, expected_bpsk_index=BPSK_INDEX,
                      expected_4ask_index=FOUR_ASK_INDEX):
    """Judge all rounds for one bandwidth level.  Returns a dict summary."""
    rounds = _rounds_for_bandwidth(sweep_dir, bandwidth_hz)
    if set(rounds.keys()) != set(range(1, ROUNDS + 1)):
        raise CheckError("bandwidth %d: need rounds 1..%d, got %s"
                         % (bandwidth_hz, ROUNDS, sorted(rounds)))
    round_results = {}
    residual = {"BPSK": [], "4ASK": []}
    corr = {"BPSK": [], "4ASK": []}
    clipped = 0
    excluded = 0
    for r in sorted(rounds):
        log_path = os.path.join(rounds[r], "run.log")
        if not os.path.isfile(log_path):
            raise CheckError("bandwidth %d round %d: missing %s"
                             % (bandwidth_hz, r, log_path))
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        rl = parse_log_text(text)
        ok, checks = judge_round(rl, bandwidth_hz, expected_bpsk_index,
                                 expected_4ask_index)
        round_results[r] = {"ok": ok, "checks": checks}
        by_mod = _sample_by_modulation(rl)
        for mod in ("BPSK", "4ASK"):
            s = by_mod.get(mod)
            if s is None:
                continue
            if s.get("payload_training_residual") is not None:
                residual[mod].append(s["payload_training_residual"])
            if s.get("payload_training_corr") is not None:
                corr[mod].append(s["payload_training_corr"])
            if s.get("rx_clipped") == 1:
                clipped += 1
        # rf_excluded comes from the two-sample summary.
        excluded += _i(rl.two_sample, "rf_excluded", "TWO_SAMPLE_RESULT")
    pass_rounds = sum(1 for v in round_results.values() if v["ok"])
    return {
        "bandwidth_hz": bandwidth_hz,
        "pass_rounds": pass_rounds,
        "total_rounds": ROUNDS,
        "round_results": round_results,
        "bpsk_residual_min_median_max": _min_med_max(residual["BPSK"]),
        "4ask_residual_min_median_max": _min_med_max(residual["4ASK"]),
        "bpsk_corr_min_median_max": _min_med_max(corr["BPSK"]),
        "4ask_corr_min_median_max": _min_med_max(corr["4ASK"]),
        "clipped_count": clipped,
        "excluded_count": excluded,
    }


def _min_med_max(values):
    if not values:
        return (None, None, None)
    return (min(values), statistics.median(values), max(values))


def select_candidate(bandwidth_summaries):
    """Return the WIDEST bandwidth (largest Hz) whose pass_rounds == ROUNDS, else None.

    `bandwidth_summaries` is a list of the analyze_bandwidth() dicts.  Selection is by
    descending Hz so ties always favour the widest level, never the narrowest."""
    passing = [s for s in bandwidth_summaries if s["pass_rounds"] == ROUNDS]
    if not passing:
        return None
    return max(passing, key=lambda s: s["bandwidth_hz"])


def analyze_sweep(sweep_dir, expected_bpsk_index=BPSK_INDEX,
                  expected_4ask_index=FOUR_ASK_INDEX):
    """Analyze a full sweep directory.  Returns a dict."""
    if not os.path.isdir(sweep_dir):
        raise CheckError("sweep dir not found: %s" % sweep_dir)
    summaries = []
    for hz in BANDWIDTH_LEVELS_HZ:
        summaries.append(analyze_bandwidth(sweep_dir, hz, expected_bpsk_index,
                                           expected_4ask_index))
    candidate = select_candidate(summaries)
    return {"sweep_dir": sweep_dir, "bandwidths": summaries,
            "candidate_hz": candidate["bandwidth_hz"] if candidate else None}


def _fmt_mmm(mmm):
    lo, med, hi = mmm
    if lo is None:
        return "n/a"
    return "min=%.6f median=%.6f max=%.6f" % (lo, med, hi)


def print_report(result):
    for b in result["bandwidths"]:
        hz = b["bandwidth_hz"]
        print("BANDWIDTH %d Hz: pass_rounds=%d/%d"
              % (hz, b["pass_rounds"], b["total_rounds"]))
        for r in sorted(b["round_results"]):
            rr = b["round_results"][r]
            print("  round %d: %s" % (r, "PASS" if rr["ok"] else "FAIL"))
            if not rr["ok"]:
                for c in rr["checks"]:
                    if c.endswith("=FAIL"):
                        print("    - %s" % c)
        print("  BPSK  residual %s" % _fmt_mmm(b["bpsk_residual_min_median_max"]))
        print("  4ASK  residual %s" % _fmt_mmm(b["4ask_residual_min_median_max"]))
        print("  BPSK  corr     %s" % _fmt_mmm(b["bpsk_corr_min_median_max"]))
        print("  4ASK  corr     %s" % _fmt_mmm(b["4ask_corr_min_median_max"]))
        print("  clipped=%d excluded=%d" % (b["clipped_count"], b["excluded_count"]))
    if result["candidate_hz"] is not None:
        print("CANDIDATE_RX_BANDWIDTH=%d" % result["candidate_hz"])
    else:
        print("CANDIDATE_RX_BANDWIDTH=NO_STABLE_RX_BANDWIDTH")


def main(argv):
    sweep_dir = argv[0] if argv else "."
    try:
        result = analyze_sweep(sweep_dir)
    except CheckError as e:
        print("CHECK_FIX10CLASS24_RX_FRONTEND_SWEEP result=ERROR reason=%s" % e)
        return 2
    print_report(result)
    return 0 if result["candidate_hz"] is not None else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
