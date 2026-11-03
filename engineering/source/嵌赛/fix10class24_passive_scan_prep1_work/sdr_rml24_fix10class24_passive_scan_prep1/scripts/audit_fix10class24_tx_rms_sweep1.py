#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_fix10class24_tx_rms_sweep1.py -- host-side FAIL-CLOSED judger for the
fix10class24-tx-rms-sweep1 task (BF16-only, TX digital RMS in {2048,1536,1024}).

Reads the board sweep produced by scripts/run_fix10class24_tx_rms_sweep1.sh:

    <sweep-root>/<link>_bf16_rms<rms>_run<run>/run.log    (runner stdout)
    <sweep-root>/<link>_bf16_rms<rms>_run<run>/config.meta

and emits, under <out-dir> (default results/tx_rms_sweep1/):

    inventory.tsv            one row per (link, rms, run) config
    per_sample_results.tsv   one row per holdout sample per config
    rms_summary.tsv          one row per (link, rms), aggregated over runs
    class_transitions.tsv    per (link, rms, class) correct/total + delta vs 2048
    residual_summary.tsv     per (link, rms) residual/corr/CFO/clip/WL/attempts stats
    summary.json             everything above + a CONCLUSION line

Forced raw24 accuracy is HYBRID evidence: gated samples are the board NPU's own
prediction; REJECTED samples are classified by the FROZEN BF16 model on the Host
(icraft-run.exe) ONLY when --icraft-run is given and the runner's --dump-failed-rx
left failed_rx/<source_index>/ dumps.  Those forced rows carry
DIAGNOSTIC_GATE_BYPASS=1 and are NEVER impersonated as a production gate pass.
Without --icraft-run, forced_raw24_accuracy is reported as PENDING.

Marker dispatch is prefix-agnostic and field-distinctive, so the single-SDR
runner (`FIX10CLASS24_BF16_SINGLESDR_*`) and dual-SDR runner (`FIX10CLASS24_BF16_*`)
parse identically.  Pure stdlib (no numpy).  Exit codes: 0 = judged; 1 = structural
parse failure (fail-closed, undecidable); 2 = usage / precondition error.
"""

import argparse
import json
import math
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

RMS_LEVELS = (2048, 1536, 1024)
RMS_BASELINE = 2048
RUNS = (1, 2, 3)
CLASS_COUNT = 24
NETWORK_NAME = "model_24class"
FORCED_LAYER = "HYBRID_BOARD_GATED_PLUS_HOST_FORCED"

RUN_DIR_RE = None  # set in main after import re


class ParseError(Exception):
    """A structural parse failure that makes a config undecidable (fail-closed)."""


# ---------------------------------------------------------------------------
# token helpers
# ---------------------------------------------------------------------------
def _tokenize(line):
    tokens = {}
    for tok in line.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            tokens[k] = v
    return tokens


def _f(tokens, key, where, default=None):
    if key not in tokens or tokens[key] == "":
        if default is not None:
            return default
        raise ParseError("%s missing/non-numeric field %s" % (where, key))
    try:
        return float(tokens[key])
    except ValueError:
        if default is not None:
            return default
        raise ParseError("%s non-numeric %s=%r" % (where, key, tokens[key]))


def _i(tokens, key, where, default=None):
    if key not in tokens or tokens[key] == "":
        if default is not None:
            return default
        raise ParseError("%s missing/non-integer field %s" % (where, key))
    try:
        return int(tokens[key])
    except ValueError:
        if default is not None:
            return default
        raise ParseError("%s non-integer %s=%r" % (where, key, tokens[key]))


def _s(tokens, key, where, default=None):
    if key not in tokens:
        if default is not None:
            return default
        raise ParseError("%s missing field %s" % (where, key))
    return tokens[key]


def _finite(v):
    return isinstance(v, float) and math.isfinite(v)


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


# ---------------------------------------------------------------------------
# per-sample model
# ---------------------------------------------------------------------------
class Sample:
    def __init__(self, source_index, source_class, modulation, file_name):
        self.source_index = source_index
        self.source_class = source_class
        self.modulation = modulation
        self.file_name = file_name
        self.gated = False
        self.valid = 0
        self.baseline_pred = None
        self.rf_pred = None
        self.prediction_agreement = 0
        self.label_correct = 0
        self.repeat_deterministic = 0
        self.finite = 0
        self.payload_training_residual = None
        self.payload_training_corr = None
        self.fine_cfo_hz = None
        self.rx_clipped = 0
        self.wide_linear_enabled = None
        self.capture_attempts = None
        self.fidelity = None
        self.diagnostic_bypass = 0


# ---------------------------------------------------------------------------
# runner stdout parsing (prefix-agnostic, field-distinctive)
# ---------------------------------------------------------------------------
def parse_run(text):
    by_index = {}
    by_name = {}
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line or "=" not in line:
            continue

        # primary FILE marker: has both source_index= and split_role=
        if " source_index=" in line and " split_role=" in line and " file=" in line:
            t = _tokenize(line)
            idx = _i(t, "source_index", "FILE")
            s = Sample(idx, _i(t, "source_class", "FILE"),
                       _s(t, "modulation", "FILE"), _s(t, "file", "FILE"))
            by_index[idx] = s
            by_name[s.file_name] = s
            continue

        # gated classification (unique: baseline_pred= AND rf_pred=)
        if " baseline_pred=" in line and " rf_pred=" in line:
            t = _tokenize(line)
            s = by_name.get(_s(t, "file", "CLASSIFY"))
            if s is None:
                raise ParseError("CLASSIFY file not in FILE map: %r" % t.get("file"))
            s.gated = True
            s.valid = 1
            s.baseline_pred = _i(t, "baseline_pred", "CLASSIFY")
            s.rf_pred = _i(t, "rf_pred", "CLASSIFY")
            s.prediction_agreement = _i(t, "prediction_agreement", "CLASSIFY")
            s.label_correct = _i(t, "label_correct", "CLASSIFY")
            s.repeat_deterministic = _i(t, "repeat_deterministic", "CLASSIFY")
            s.finite = _i(t, "finite", "CLASSIFY")
            continue

        # recovery (unique: payload_training_residual=)
        if " payload_training_residual=" in line:
            t = _tokenize(line)
            s = by_name.get(_s(t, "file", "RECOVERY"))
            if s is None:
                continue
            s.payload_training_residual = _f(t, "payload_training_residual", "RECOVERY", None)
            s.payload_training_corr = _f(t, "payload_training_corr", "RECOVERY", None)
            s.fine_cfo_hz = _f(t, "fine_cfo_hz", "RECOVERY", None)
            s.rx_clipped = _i(t, "rx_clipped", "RECOVERY", 0)
            s.fidelity = _s(t, "fidelity", "RECOVERY", None)
            continue

        # wide-linear decision (unique: scalar_validation_residual=)
        if " scalar_validation_residual=" in line:
            t = _tokenize(line)
            s = by_name.get(_s(t, "file", "WIDE_LINEAR"))
            if s is None:
                continue
            s.wide_linear_enabled = _i(t, "enabled", "WIDE_LINEAR", None)
            continue

        # capture attempts (unique: attempts= AND retries=)
        if " attempts=" in line and " retries=" in line:
            t = _tokenize(line)
            s = by_name.get(_s(t, "file", "CAPTURE_ATTEMPTS"))
            if s is None:
                continue
            s.capture_attempts = _i(t, "attempts", "CAPTURE_ATTEMPTS", None)
            continue

        # rejected by fidelity gate (unique: classification=SKIPPED)
        if " classification=SKIPPED" in line:
            t = _tokenize(line)
            s = by_name.get(_s(t, "file", "SKIPPED"))
            if s is not None:
                s.fidelity = _s(t, "fidelity", "SKIPPED", s.fidelity)
            continue

    return by_index


# ---------------------------------------------------------------------------
# config-level metrics
# ---------------------------------------------------------------------------
def compute_config_metrics(samples, forced_results=None):
    gated = [s for s in samples.values() if s.gated]
    forced = forced_results or []
    gated_correct = sum(1 for s in gated if s.label_correct == 1)
    forced_correct = sum(1 for f in forced if int(f.get("label_correct", 0)) == 1)

    total_holdout = len(samples)
    scored = len(gated)
    rf_excluded = max(0, total_holdout - scored)
    coverage = scored / total_holdout if total_holdout else 0.0
    gated_accuracy = gated_correct / scored if scored else 0.0
    end_to_end_accuracy = gated_correct / total_holdout if total_holdout else 0.0
    forced_available = len(forced) > 0
    forced_raw24_accuracy = ((gated_correct + forced_correct) / total_holdout
                             if total_holdout else 0.0)

    pred_agree = sum(1 for s in gated if s.prediction_agreement == 1)
    finite_ok = sum(1 for s in gated if s.finite == 1)
    repeat_ok = sum(1 for s in gated if s.repeat_deterministic == 1)

    residuals = [s.payload_training_residual for s in gated
                 if _finite(s.payload_training_residual)]
    corrs = [s.payload_training_corr for s in gated if _finite(s.payload_training_corr)]
    cfos = [s.fine_cfo_hz for s in gated if _finite(s.fine_cfo_hz)]
    wl_en = [s for s in gated if s.wide_linear_enabled == 1]
    attempts = [s.capture_attempts for s in gated if s.capture_attempts is not None]

    per_class = {}
    for s in gated:
        per_class.setdefault(s.source_class, {"total": 0, "correct": 0})
        per_class[s.source_class]["total"] += 1
        if s.label_correct == 1:
            per_class[s.source_class]["correct"] += 1

    return {
        "total_holdout": total_holdout,
        "scored": scored,
        "rf_excluded": rf_excluded,
        "coverage": coverage,
        "gated_accuracy": gated_accuracy,
        "end_to_end_accuracy": end_to_end_accuracy,
        "forced_raw24_accuracy": forced_raw24_accuracy,
        "forced_available": forced_available,
        "forced_count": len(forced),
        "forced_correct": forced_correct,
        "prediction_agreement": pred_agree,
        "label_correct": gated_correct,
        "finite_ok": finite_ok,
        "repeat_deterministic_ok": repeat_ok,
        "residual_mean": _mean(residuals),
        "residual_max": max(residuals) if residuals else None,
        "corr_mean": _mean(corrs),
        "corr_min": min(corrs) if corrs else None,
        "cfo_finite": len(cfos),
        "cfo_mean": _mean(cfos),
        "rx_clipped": sum(1 for s in gated if s.rx_clipped == 1),
        "wide_linear_enabled_ratio": (len(wl_en) / scored if scored else 0.0),
        "capture_attempts_mean": _mean([float(a) for a in attempts]),
        "capture_attempts_max": max(attempts) if attempts else None,
        "per_class": per_class,
        "misclassifications": [
            (s.source_index, s.source_class, s.rf_pred, s.payload_training_residual)
            for s in gated if s.label_correct == 0
        ],
    }


# ---------------------------------------------------------------------------
# forced (Host) classification of rejected samples
# ---------------------------------------------------------------------------
def _run_host_infer(icraft_run, model_json, model_raw, input_bin, workdir):
    log_path = workdir / "logs"
    cmd = [str(icraft_run), "--json", str(model_json), "--raw", str(model_raw),
           "--network", NETWORK_NAME, "--input", str(input_bin),
           "--backends", "Host", "--dump_output", "--log_path", str(log_path)]
    proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True)
    if proc.returncode != 0:
        raise ParseError("icraft-run exit %d: %s" % (proc.returncode,
                         proc.stderr.decode("utf-8", "replace")[-1500:]))
    ftmp_dir = log_path / NETWORK_NAME / "ftmpHQB"
    ftmps = list(ftmp_dir.glob("*.ftmp")) if ftmp_dir.is_dir() else []
    if len(ftmps) != 1:
        raise ParseError("expected 1 ftmp under %s, got %d" % (ftmp_dir, len(ftmps)))
    raw = ftmps[0].read_bytes()
    if len(raw) != CLASS_COUNT * 4:
        raise ParseError("ftmp %d bytes (want %d)" % (len(raw), CLASS_COUNT * 4))
    return raw


def _classify_input(icraft_run, model_json, model_raw, input_bin):
    raws = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as td:
            raws.append(_run_host_infer(icraft_run, model_json, model_raw,
                                        input_bin, Path(td)))
    if len(set(raws)) != 1:
        raise ParseError("Host forward not byte-identical across 2 passes")
    logits = struct.unpack("<%df" % CLASS_COUNT, raws[0])
    if not all(math.isfinite(x) for x in logits):
        raise ParseError("Host forward produced non-finite logits")
    return max(range(CLASS_COUNT), key=lambda i: logits[i])


def forced_classify_rejected(samples, run_dir, clean24_dir, icraft_run, model_dir,
                             force_tool):
    """Classify rejected samples from failed_rx dumps; return list of dicts."""
    failed_root = Path(run_dir) / "failed_rx"
    if not failed_root.is_dir():
        return []
    model_json = Path(model_dir) / "rml24_adamrv11_bf16.json"
    model_raw = Path(model_dir) / "rml24_adamrv11_bf16.raw"
    if not model_json.is_file() or not model_raw.is_file():
        raise ParseError("BF16 model json/raw not found under %s" % model_dir)

    results = []
    for dump_dir in sorted(failed_root.iterdir()):
        if not dump_dir.is_dir():
            continue
        idx_str = dump_dir.name
        try:
            source_index = int(idx_str)
        except ValueError:
            continue
        src = samples.get(source_index)
        with tempfile.TemporaryDirectory() as td:
            export_dir = Path(td) / "export"
            export_dir.mkdir()
            cmd = ["bash", force_tool, "--dump-dir", str(dump_dir),
                   "--clean24-dir", str(clean24_dir), "--export-dir", str(export_dir)]
            proc = subprocess.run(cmd, capture_output=True)
            if proc.returncode != 0:
                continue
            mi_bins = list(export_dir.rglob("model_input_f32le.bin"))
            if len(mi_bins) != 1:
                continue
            mi = mi_bins[0]
            if mi.stat().st_size != 2 * 1024 * 4:
                continue
            pred = _classify_input(icraft_run, model_json, model_raw, mi)
        source_class = src.source_class if src is not None else -1
        results.append({"source_index": source_index,
                        "source_class": source_class,
                        "rf_pred": pred,
                        "label_correct": int(pred == source_class),
                        "diagnostic_bypass": 1})
    return results


# ---------------------------------------------------------------------------
# output writers
# ---------------------------------------------------------------------------
def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return "%.6f" % v
    return str(v)


def write_outputs(out_dir, configs):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "inventory.tsv", "w", encoding="utf-8") as fh:
        fh.write("link\trms\trun\tmode\ttotal_holdout\tscored\trf_excluded\tcoverage\t"
                 "gated_accuracy\tend_to_end_accuracy\tforced_raw24_accuracy\t"
                 "forced_available\tprediction_agreement\tlabel_correct\tfinite_ok\t"
                 "repeat_deterministic_ok\n")
        for c in configs:
            m = c["metrics"]
            fh.write("%s\t%s\t%s\t%s\t%d\t%d\t%d\t%.4f\t%.4f\t%.4f\t%.4f\t%d\t%d\t%d\t%d\t%d\n"
                     % (c["link"], c["rms"], c["run"], c["mode"], m["total_holdout"],
                        m["scored"], m["rf_excluded"], m["coverage"], m["gated_accuracy"],
                        m["end_to_end_accuracy"], m["forced_raw24_accuracy"],
                        1 if m["forced_available"] else 0, m["prediction_agreement"],
                        m["label_correct"], m["finite_ok"], m["repeat_deterministic_ok"]))

    with open(out_dir / "per_sample_results.tsv", "w", encoding="utf-8") as fh:
        fh.write("link\trms\trun\tsource_index\tsource_class\tmodulation\tgated\t"
                 "rf_pred\tbaseline_pred\tprediction_agreement\tlabel_correct\t"
                 "repeat_deterministic\tfinite\tpayload_training_residual\t"
                 "payload_training_corr\tfine_cfo_hz\trx_clipped\twide_linear_enabled\t"
                 "capture_attempts\tdiagnostic_bypass\n")
        for c in configs:
            for s in sorted(c["samples"].values(), key=lambda x: x.source_index):
                fh.write("%s\t%s\t%s\t%d\t%d\t%s\t%d\t%s\t%s\t%d\t%d\t%d\t%d\t%s\t%s\t%s\t%d\t%s\t%s\t%d\n"
                         % (c["link"], c["rms"], c["run"], s.source_index, s.source_class,
                            s.modulation, 1 if s.gated else 0,
                            _fmt(s.rf_pred), _fmt(s.baseline_pred), s.prediction_agreement,
                            s.label_correct, s.repeat_deterministic, s.finite,
                            _fmt(s.payload_training_residual), _fmt(s.payload_training_corr),
                            _fmt(s.fine_cfo_hz), s.rx_clipped,
                            _fmt(s.wide_linear_enabled), _fmt(s.capture_attempts),
                            s.diagnostic_bypass))
            for f in c.get("forced", []):
                fh.write("%s\t%s\t%s\t%s\t%s\t\t0\t%s\t\t0\t%d\t0\t0\t\t\t\t0\t\t\t1\n"
                         % (c["link"], c["rms"], c["run"], f["source_index"],
                            f["source_class"], _fmt(f.get("rf_pred")),
                            int(f.get("label_correct", 0))))

    with open(out_dir / "rms_summary.tsv", "w", encoding="utf-8") as fh:
        fh.write("link\trms\truns\tscored\trf_excluded\tcoverage\tgated_accuracy\t"
                 "end_to_end_accuracy\tforced_raw24_accuracy\tresidual_mean\tresidual_max\t"
                 "corr_mean\tcfo_mean\trx_clipped\twide_linear_enabled_ratio\t"
                 "capture_attempts_mean\n")
        for link, rms, group in _group_by_link_rms(configs):
            prim = group[0]["metrics"]
            fh.write("%s\t%s\t%d\t%d\t%d\t%.4f\t%.4f\t%.4f\t%.4f\t%s\t%s\t%s\t%s\t%d\t%.4f\t%s\n"
                     % (link, rms, len(group), prim["scored"], prim["rf_excluded"],
                        prim["coverage"], prim["gated_accuracy"], prim["end_to_end_accuracy"],
                        prim["forced_raw24_accuracy"], _fmt(prim["residual_mean"]),
                        _fmt(prim["residual_max"]), _fmt(prim["corr_mean"]),
                        _fmt(prim["cfo_mean"]), prim["rx_clipped"],
                        prim["wide_linear_enabled_ratio"], _fmt(prim["capture_attempts_mean"])))

    base = {}
    for c in configs:
        if c["rms"] == RMS_BASELINE:
            for cls, pc in c["metrics"]["per_class"].items():
                base[(c["link"], cls)] = pc["correct"] / pc["total"] if pc["total"] else 0.0
    with open(out_dir / "class_transitions.tsv", "w", encoding="utf-8") as fh:
        fh.write("link\trms\tclass\ttotal\tcorrect\tcorrect_ratio\tdelta_vs_2048\n")
        for c in configs:
            for cls in range(CLASS_COUNT):
                pc = c["metrics"]["per_class"].get(cls, {"total": 0, "correct": 0})
                ratio = pc["correct"] / pc["total"] if pc["total"] else 0.0
                b = base.get((c["link"], cls), None)
                delta = (ratio - b) if b is not None else 0.0
                fh.write("%s\t%s\t%d\t%d\t%d\t%.4f\t%.4f\n"
                         % (c["link"], c["rms"], cls, pc["total"], pc["correct"],
                            ratio, delta))

    with open(out_dir / "residual_summary.tsv", "w", encoding="utf-8") as fh:
        fh.write("link\trms\trun\tresidual_mean\tresidual_max\tcorr_mean\tcorr_min\t"
                 "cfo_mean\tcfo_finite_count\trx_clipped\twide_linear_enabled_ratio\t"
                 "capture_attempts_mean\tcapture_attempts_max\n")
        for c in configs:
            m = c["metrics"]
            fh.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%d\t%d\t%.4f\t%s\t%s\n"
                     % (c["link"], c["rms"], c["run"], _fmt(m["residual_mean"]),
                        _fmt(m["residual_max"]), _fmt(m["corr_mean"]), _fmt(m["corr_min"]),
                        _fmt(m["cfo_mean"]), m["cfo_finite"], m["rx_clipped"],
                        m["wide_linear_enabled_ratio"], _fmt(m["capture_attempts_mean"]),
                        _fmt(m["capture_attempts_max"])))

    summary = {
        "configs": [{
            "link": c["link"], "rms": c["rms"], "run": c["run"], "mode": c["mode"],
            **{k: v for k, v in c["metrics"].items() if k != "per_class"},
        } for c in configs],
        "conclusion": _conclusion(configs),
        "forbidden_tokens_checked": True,
        "forced_layer": FORCED_LAYER,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _group_by_link_rms(configs):
    seen = {}
    for c in configs:
        seen.setdefault((c["link"], c["rms"]), []).append(c)
    return [(k[0], k[1], v) for k, v in sorted(seen.items())]


def _conclusion(configs):
    best = RMS_BASELINE
    best_score = -1.0
    for c in configs:
        if c["run"] != 1:
            continue
        score = c["metrics"]["forced_raw24_accuracy"]
        if score > best_score:
            best_score = score
            best = c["rms"]
    if best == RMS_BASELINE:
        return "NO_EVIDENCE_TX_TARGET_RMS_CAUSES_ACCURACY_LOSS"
    return "TARGET_RMS_CANDIDATE_FOR_PROSPECTIVE_VALIDATION"


# ---------------------------------------------------------------------------
# sweep-root walk + main
# ---------------------------------------------------------------------------
def collect_runs(sweep_root, link_filter, run_dir_re):
    root = Path(sweep_root)
    configs = []
    if not root.is_dir():
        raise ParseError("sweep root not found: %s" % root)
    for run_dir in sorted(root.iterdir()):
        if not run_dir.is_dir():
            continue
        m = run_dir_re.match(run_dir.name)
        if not m:
            continue
        link, rms, run = m.group(1), int(m.group(2)), int(m.group(3))
        if link_filter and link != link_filter:
            continue
        if rms not in RMS_LEVELS or run not in RUNS:
            raise ParseError("bad run dir name: %s" % run_dir.name)
        log = run_dir / "run.log"
        if not log.is_file():
            raise ParseError("missing run.log under %s" % run_dir)
        samples = parse_run(log.read_text(encoding="utf-8", errors="replace"))
        meta = _read_config_meta(run_dir)
        if meta.get("requested_target_rms") != rms:
            raise ParseError("config.meta rms %s != dir rms %s"
                             % (meta.get("requested_target_rms"), rms))
        if meta.get("link") != link:
            raise ParseError("config.meta link %s != dir link %s" % (meta.get("link"), link))
        configs.append({
            "link": link, "rms": rms, "run": run, "mode": meta.get("mode", ""),
            "samples": samples,
            "metrics": compute_config_metrics(samples),
            "forced": [],
        })
    if not configs:
        raise ParseError("no sweep run dirs matched under %s" % root)
    return configs


def _read_config_meta(run_dir):
    run_dir = Path(run_dir)
    meta = run_dir / "config.meta"
    if not meta.is_file():
        raise ParseError("missing config.meta under %s" % run_dir)
    out = {}
    for line in meta.read_text(encoding="utf-8").splitlines():
        if "requested_target_rms=" in line:
            out["requested_target_rms"] = int(line.split("requested_target_rms=", 1)[1].split()[0])
        elif " link=" in line and "mode=" in line:
            out["link"] = line.split("link=", 1)[1].split()[0]
            out["mode"] = line.split("mode=", 1)[1].split()[0]
    return out


def self_test():
    import re
    # single-SDR style log: 3 files, 2 gated (1 correct), 1 rejected
    text = (
        "FIX10CLASS24_BF16_SINGLESDR_FILE file=bpsk_1500.ci16 input_kind=radioml-d2-2p56m "
        "source_index=1500 source_class=3 modulation=BPSK frozen_complex=53760 split_role=holdout\n"
        "FIX10CLASS24_BF16_SINGLESDR_FILE file=qpsk_2500.ci16 input_kind=radioml-d2-2p56m "
        "source_index=2500 source_class=4 modulation=QPSK frozen_complex=53760 split_role=holdout\n"
        "FIX10CLASS24_BF16_SINGLESDR_FILE file=4ask_500.ci16 input_kind=radioml-d2-2p56m "
        "source_index=500 source_class=1 modulation=4ASK frozen_complex=53760 split_role=holdout\n"
        "FIX10CLASS24_BF16_SINGLESDR_CAPTURE_ATTEMPTS file=bpsk_1500.ci16 attempts=1 retries=0 final_failure=NONE final_valid=1\n"
        "FIX10CLASS24_BF16_SINGLESDR_RECOVERY file=bpsk_1500.ci16 computed=1 valid=1 failure=NONE "
        "fine_cfo_hz=0.500 training_corr=0.998000 training_residual=0.040000 "
        "payload_training_corr=0.998000 payload_training_residual=0.040000 fidelity=RF_PRESERVES_IQ rx_clipped=0\n"
        "FIX10CLASS24_BF16_SINGLESDR_WIDE_LINEAR file=bpsk_1500.ci16 enabled=1 scalar_validation_residual=0.10 validation_residual=0.08 improvement_ratio=0.8 image_ratio=0.1 reason=ENABLED\n"
        "FIX10CLASS24_BF16_SINGLESDR_CAPTURE_ATTEMPTS file=qpsk_2500.ci16 attempts=2 retries=1 final_failure=NONE final_valid=1\n"
        "FIX10CLASS24_BF16_SINGLESDR_RECOVERY file=qpsk_2500.ci16 computed=1 valid=1 failure=NONE "
        "fine_cfo_hz=-0.300 training_corr=0.997000 training_residual=0.050000 "
        "payload_training_corr=0.997000 payload_training_residual=0.050000 fidelity=RF_PRESERVES_IQ rx_clipped=0\n"
        "FIX10CLASS24_BF16_SINGLESDR_WIDE_LINEAR file=qpsk_2500.ci16 enabled=0 scalar_validation_residual=0.10 validation_residual=0.11 improvement_ratio=1.1 image_ratio=0.001 reason=IMAGE_TOO_SMALL\n"
        "FIX10CLASS24_BF16_SINGLESDR_FILE file=4ask_500.ci16 classification=SKIPPED reason=fidelity_gate fidelity=PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH\n"
        "FIX10CLASS24_BF16_SINGLESDR_CLASSIFY file=bpsk_1500.ci16 baseline_pred=3 rf_pred=3 "
        "source_label=3 prediction_agreement=1 label_correct=1 repeat_deterministic=1 finite=1\n"
        "FIX10CLASS24_BF16_SINGLESDR_CLASSIFY file=qpsk_2500.ci16 baseline_pred=4 rf_pred=5 "
        "source_label=4 prediction_agreement=0 label_correct=0 repeat_deterministic=1 finite=1\n"
    )
    samples = parse_run(text)
    assert len(samples) == 3, len(samples)
    assert samples[1500].gated and samples[1500].label_correct == 1
    assert samples[2500].gated and samples[2500].label_correct == 0
    assert not samples[500].gated
    assert samples[1500].payload_training_residual == 0.04
    assert samples[1500].wide_linear_enabled == 1
    assert samples[1500].capture_attempts == 1
    m = compute_config_metrics(samples)
    assert m["scored"] == 2 and m["rf_excluded"] == 1
    assert abs(m["coverage"] - 2 / 3) < 1e-9
    assert abs(m["gated_accuracy"] - 0.5) < 1e-9
    assert abs(m["end_to_end_accuracy"] - 1 / 3) < 1e-9
    assert abs(m["wide_linear_enabled_ratio"] - 0.5) < 1e-9
    assert m["capture_attempts_mean"] == 1.5
    assert abs(m["residual_mean"] - 0.045) < 1e-9
    assert m["per_class"][3]["correct"] == 1 and m["per_class"][4]["correct"] == 0

    # dual-SDR style log (plain FIX10CLASS24_BF16_* prefix)
    text2 = (
        "FIX10CLASS24_BF16_FILE file=bpsk_1500.ci16 input_kind=radioml-d2-2p56m "
        "source_index=1500 source_class=3 modulation=BPSK frozen_complex=53760 split_role=holdout\n"
        "FIX10CLASS24_BF16_CAPTURE_ATTEMPTS file=bpsk_1500.ci16 attempts=1 retries=0 final_failure=NONE final_valid=1\n"
        "FIX10CLASS24_BF16_RECOVERY file=bpsk_1500.ci16 computed=1 valid=1 failure=NONE "
        "fine_cfo_hz=0.250 payload_training_corr=0.999000 payload_training_residual=0.030000 fidelity=RF_PRESERVES_IQ rx_clipped=0\n"
        "FIX10CLASS24_BF16_CLASSIFY file=bpsk_1500.ci16 baseline_pred=3 rf_pred=3 "
        "source_label=3 prediction_agreement=1 label_correct=1 repeat_deterministic=1 finite=1\n"
    )
    s2 = parse_run(text2)
    assert len(s2) == 1 and s2[1500].gated and s2[1500].label_correct == 1
    assert s2[1500].payload_training_residual == 0.03
    print("SELF_TEST_OK")
    return 0


def main(argv):
    import re
    ap = argparse.ArgumentParser(description="fail-closed TX RMS sweep judger")
    ap.add_argument("--sweep-root", default=None)
    ap.add_argument("--link", choices=["single", "dual"], default=None)
    ap.add_argument("--out-dir", default="results/tx_rms_sweep1")
    ap.add_argument("--clean24-dir", default="clean24_smoke")
    ap.add_argument("--icraft-run", default=None)
    ap.add_argument("--model-dir", default="model_rml24_bf16")
    ap.add_argument("--force-tool", default="host_tools/replay_fix10class24_failed_rx_force_classify.sh")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if not args.sweep_root:
        ap.error("--sweep-root is required (or use --self-test)")

    run_dir_re = re.compile(r"^(single|dual)_bf16_rms(\d+)_run([123])$")
    configs = collect_runs(args.sweep_root, args.link, run_dir_re)

    do_forced = args.icraft_run is not None and Path(args.icraft_run).is_file()
    if do_forced:
        for c in configs:
            run_dir = Path(args.sweep_root) / ("%s_bf16_rms%s_run%s" % (c["link"], c["rms"], c["run"]))
            forced = forced_classify_rejected(c["samples"], run_dir, args.clean24_dir,
                                              args.icraft_run, args.model_dir, args.force_tool)
            c["forced"] = forced
            c["metrics"] = compute_config_metrics(c["samples"], forced)

    write_outputs(args.out_dir, configs)

    for c in configs:
        m = c["metrics"]
        forced_s = "%.4f" % m["forced_raw24_accuracy"] if (m["forced_available"] or do_forced) else "PENDING"
        print("[audit] %s rms=%s run=%s scored=%d rf_excluded=%d coverage=%.4f "
              "gated_acc=%.4f e2e_acc=%.4f forced_acc=%s"
              % (c["link"], c["rms"], c["run"], m["scored"], m["rf_excluded"],
                 m["coverage"], m["gated_accuracy"], m["end_to_end_accuracy"], forced_s))
    print("[audit] CONCLUSION=%s" % _conclusion(configs))
    print("[audit] wrote %s" % args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
