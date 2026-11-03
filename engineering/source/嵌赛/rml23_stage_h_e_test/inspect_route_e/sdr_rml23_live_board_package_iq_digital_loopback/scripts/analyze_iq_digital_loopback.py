#!/usr/bin/env python3
"""analyze_iq_digital_loopback.py -- Stage H-E / Route E analyzer.

Reads the board's Route E producer log (board_gate9_full_chain_rml23.cpp,
--phase=iq-digital-loopback) and re-derives the three SEPARATE verdicts as an
independent host-side record (Stage H-E hard requirement 11: infrastructure /
fidelity / classification are never conflated):

  * infrastructure -- device config / TX / RX / sync / capture / restore,
    recovered from the sample-rate, loopback, attenuation read-back, capture_ok
    and restore_result tokens (PASS/FAIL gates only);
  * fidelity      -- per-file NMSE / EVM / CFO / correlation plus the observation
    token (DIGITAL_LOOPBACK_PRESERVES_IQ / DISTORTS_IQ / SYNC_OR_WRAP_INCONCLUSIVE
    / DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN / INSUFFICIENT_EVIDENCE);
  * classification-- per-file frames/correct and the aggregate verdict token
    (CLASS_CONSISTENT_WITH_FROZEN_REFERENCE / CLASS_FLIPPED_PREPROCESS_DIVERGENCE
    / CLASS_MAJORITY_DEPLOYED / CLASS_DIVERGENT / INSUFFICIENT_EVIDENCE),
    measurement-only.

It NEVER issues an accuracy PASS/FAIL and NEVER promotes arbitrary_modulated_iq_
fidelity from BOARD_REQUIRED: that token stays BOARD_REQUIRED until a board run
reports PRESERVES_IQ / DISTORTS_IQ, which this analyzer only re-reports (never
invents).  Classification errors never fail infrastructure and vice versa.

Inputs:
  --log LOG        board producer stdout (repeatable, or pass a directory of
                   *.log).  The GATE_RESULT line is also accepted.
  --frozen-dir DIR (optional) Stage G artifacts dir; independently re-verifies
                   every frozen .ci16 SHA/size against its manifest.
  --input-kind K   (optional) filter to one input kind.
  --json PATH      write the full machine-readable record here.

stdlib only.  Run isolated:  python -I analyze_iq_digital_loopback.py ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

FROZEN_FS = 2560000
RATE_TOL_HZ = 5

# Frozen 24-class source -> 23-class deployed mapping (== rml23::kSourceToDeployed).
SOURCE_TO_DEPLOYED = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
    17, 17, 18, 19, 20, 21, 22,
]


def parse_kv(line: str) -> dict:
    """All space-separated key=value tokens (value kept as str)."""
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


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_logs(log_args) -> list:
    """Expand --log args (files or directories of *.log) into a line list."""
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


def verify_frozen_dir(frozen_dir: str, input_kind: str) -> dict:
    """Independently re-verify every frozen .ci16 SHA/size against its manifest."""
    out = {"dir": frozen_dir, "manifest": None, "files": [], "all_ok": True}
    if input_kind == "generated-2p56m":
        mpath = os.path.join(frozen_dir, "iq_loopback_manifest.tsv")
        cols = {"file": 0, "byte": 6, "sha": 19}
        out["manifest"] = "iq_loopback_manifest.tsv"
    elif input_kind == "radioml-reconstructed-2p56m":
        mpath = os.path.join(frozen_dir, "roundtrip_manifest.tsv")
        cols = {"file": 8}
        out["manifest"] = "roundtrip_manifest.tsv"
    else:
        out["all_ok"] = False
        out["error"] = "unknown input_kind (cannot pick a manifest)"
        return out

    if not os.path.exists(mpath):
        out["all_ok"] = False
        out["error"] = "STAGE_G_FROZEN_IQ_REQUIRED: missing " + mpath
        return out

    rows = []
    with open(mpath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) <= max(cols.values()):
                out["all_ok"] = False
                out["error"] = "malformed manifest row: " + line
                return out
            rows.append(parts)

    for parts in rows:
        fname = parts[cols["file"]]
        rec = {"file": fname}
        path = os.path.join(frozen_dir, fname)
        if not os.path.exists(path):
            rec["ok"] = False
            rec["error"] = "missing"
            out["all_ok"] = False
        else:
            got = sha256_of(path)
            size = os.path.getsize(path)
            rec["size"] = size
            rec["sha256"] = got
            rec["ok"] = True
            if "sha" in cols:
                want = parts[cols["sha"]]
                if got != want:
                    rec["ok"] = False
                    rec["error"] = "sha mismatch"
                    out["all_ok"] = False
            if "byte" in cols:
                want_bytes = to_int(parts[cols["byte"]])
                if size != want_bytes:
                    rec["ok"] = False
                    rec["error"] = "size mismatch"
                    out["all_ok"] = False
        out["files"].append(rec)
    return out


def analyze(log_args, frozen_dir, input_kind_filter):
    rec = {
        "input_kinds": {},
        "files": [],
        "arbitrary_modulated_iq_fidelity": "BOARD_REQUIRED",
        "infrastructure": {},
        "classification": {},
        "gate_result": None,
    }
    per_file = {}          # file -> accumulated record
    arb_input_kind = None
    frozen_files_reported = None

    for line in read_logs(log_args):
        if not line.strip():
            continue

        if line.startswith("ARBITRARY_MODULATED_IQ_FIDELITY"):
            d = parse_kv(line)
            arb_input_kind = d.get("input_kind")
            frozen_files_reported = to_int(d.get("frozen_files"))
            rec["frozen_dir"] = d.get("frozen_dir")
            rec["arbitrary_modulated_iq_fidelity"] = \
                line.split()[1] if len(line.split()) >= 2 else "BOARD_REQUIRED"
            continue

        if line.startswith("RF_LEAKAGE_NOT_PROVEN"):
            d = parse_kv(line)
            rec.setdefault("rf_leakage", []).append({
                "file": d.get("file"),
                "tx_atten_requested_db": to_float(d.get("tx_atten_requested_db")),
                "tx_atten_readback_db": to_float(d.get("tx_atten_readback_db")),
                "loopback": to_int(d.get("loopback")),
                "antenna": d.get("antenna", "none"),
                "coax": d.get("coax", "none"),
                "ensm": d.get("ensm", "not_managed_by_this_code"),
            })
            continue

        if line.startswith("IQ_DIGITAL_LOOPBACK"):
            d = parse_kv(line)
            fname = d.get("file", "?")
            pf = per_file.setdefault(fname, {"file": fname})
            if "fidelity" in d:
                pf["fidelity"] = {
                    "verdict": d["fidelity"],
                    "delay": to_int(d.get("delay")),
                    "gain_db": to_float(d.get("gain_db")),
                    "phase_deg": to_float(d.get("phase_deg")),
                    "nmse": to_float(d.get("nmse")),
                    "evm_pct": to_float(d.get("evm_pct")),
                    "corr": to_float(d.get("corr")),
                    "cfo_hz": to_float(d.get("cfo_hz")),
                    "phase_drift_deg": to_float(d.get("phase_drift_deg")),
                    "rms_tx": to_float(d.get("rms_tx")),
                    "rms_rx": to_float(d.get("rms_rx")),
                    "corr_swap": to_float(d.get("corr_swap")),
                    "corr_conj": to_float(d.get("corr_conj")),
                }
            elif "frames" in d:
                pf["classification"] = {
                    "frames": to_int(d.get("frames")),
                    "correct": to_int(d.get("correct")),
                    "deployed": to_int(d.get("deployed")),
                    "source": to_int(d.get("source")),
                }
            elif "capture" in d and d.get("capture") == "FAIL":
                pf["capture_ok"] = False
                pf["capture_detail"] = d.get("detail", "")
            elif "input_kind" in d:
                pf.update({
                    "input_kind": d.get("input_kind"),
                    "source_class": to_int(d.get("source_class"), -1),
                    "deployed_class": to_int(d.get("deployed_class"), -1),
                    "modulation": d.get("modulation"),
                    "tx_complex": to_int(d.get("tx_complex")),
                    "frozen_complex": to_int(d.get("frozen_complex")),
                    "frozen_frames": to_int(d.get("frozen_frames")),
                    "frozen_correct": to_int(d.get("frozen_correct")),
                })
            elif "delay+period exceeds capture" in line:
                pf["classification_error"] = "delay+period exceeds capture"
            elif "interrupted" in line:
                pf["interrupted"] = True
            continue

        if line.startswith("GATE_RESULT"):
            d = parse_kv(line)
            rec["gate_result"] = {
                "gate": d.get("gate"),
                "result": d.get("result"),
                "detail": d,
            }
            infra = rec["infrastructure"]
            infra["gate_result"] = d.get("result")
            infra["requested_rate"] = to_int(d.get("requested_rate"))
            infra["rx_rate"] = to_int(d.get("rx_rate"))
            infra["tx_rate"] = to_int(d.get("tx_rate"))
            infra["rate_err_hz"] = to_float(d.get("rate_err_hz"))
            infra["rate_err_ppm"] = to_float(d.get("rate_err_ppm"))
            infra["loopback"] = to_int(d.get("loopback"), -1)
            infra["tx_atten_requested_db"] = to_float(d.get("tx_atten_requested_db"))
            infra["tx_atten_readback_db"] = to_float(d.get("tx_atten_readback_db"))
            infra["restore_result"] = d.get("restore_result")
            infra["classification_verdict"] = d.get("classification_verdict")
            infra["classification_frames"] = to_int(d.get("classification_frames"))
            infra["classification_correct"] = to_int(d.get("classification_correct"))
            infra["frozen_frames"] = to_int(d.get("frozen_frames"))
            infra["frozen_correct"] = to_int(d.get("frozen_correct"))
            infra["has_frozen_ref"] = to_int(d.get("has_frozen_ref"))
            infra["error"] = d.get("error")
            continue

    # fold per-file records in, honouring the input-kind filter.
    for fname, pf in sorted(per_file.items()):
        ik = pf.get("input_kind")
        if input_kind_filter and ik != input_kind_filter:
            continue
        rec["files"].append(pf)

    # aggregate classification per input kind (never mixed).
    kinds = {}
    for pf in rec["files"]:
        ik = pf.get("input_kind", "?")
        k = kinds.setdefault(ik, {"frames": 0, "correct": 0, "files": 0,
                                  "frozen_frames": 0, "frozen_correct": 0,
                                  "has_frozen_ref": False})
        c = pf.get("classification", {})
        k["frames"] += c.get("frames", 0)
        k["correct"] += c.get("correct", 0)
        k["files"] += 1
        k["frozen_frames"] += pf.get("frozen_frames", 0)
        k["frozen_correct"] += pf.get("frozen_correct", 0)
        if pf.get("frozen_frames", 0) > 0:
            k["has_frozen_ref"] = True
    for ik, k in kinds.items():
        k["recovered_rate"] = (k["correct"] / k["frames"]) if k["frames"] else None
        k["frozen_rate"] = (k["frozen_correct"] / k["frozen_frames"]) \
            if k["frozen_frames"] else None
        k["verdict"] = classification_verdict(k)
    rec["input_kinds"] = kinds

    if frozen_dir and (arb_input_kind or input_kind_filter):
        rec["frozen_verify"] = verify_frozen_dir(
            frozen_dir, input_kind_filter or arb_input_kind)

    return rec


def classification_verdict(k):
    if k["frames"] == 0:
        return "INSUFFICIENT_EVIDENCE"
    rr = k["recovered_rate"]
    if k["has_frozen_ref"] and k["frozen_frames"] > 0:
        return ("CLASS_CONSISTENT_WITH_FROZEN_REFERENCE"
                if rr >= k["frozen_rate"] else
                "CLASS_FLIPPED_PREPROCESS_DIVERGENCE")
    return "CLASS_MAJORITY_DEPLOYED" if rr >= 0.5 else "CLASS_DIVERGENT"


def render(rec):
    lines = []
    a = lines.append
    a("=" * 72)
    a("Route E -- same-device modulated-IQ digital loopback (Stage H-E)")
    a("arbitrary_modulated_iq_fidelity=%s" % rec["arbitrary_modulated_iq_fidelity"])
    a("=" * 72)

    infra = rec["infrastructure"]
    a("")
    a("[1] INFRASTRUCTURE (device config / TX / RX / sync / capture / restore)")
    a("    gate_result=%s" % infra.get("gate_result", "UNKNOWN"))
    if infra.get("requested_rate"):
        a("    sample_rate requested=%d rx=%d tx=%d err=%+.3f Hz (%+.3f ppm)"
          % (infra.get("requested_rate"), infra.get("rx_rate"),
             infra.get("tx_rate"), infra.get("rate_err_hz", 0.0),
             infra.get("rate_err_ppm", 0.0)))
        ok = (abs(to_int(infra.get("rx_rate")) - infra.get("requested_rate", 0)) <= RATE_TOL_HZ
              and abs(to_int(infra.get("tx_rate")) - infra.get("requested_rate", 0)) <= RATE_TOL_HZ)
        a("    sample_rate_ok=%s (abs(actual-2560000)<=%d Hz)" % (ok, RATE_TOL_HZ))
    a("    loopback=%s (1=digital)  tx_atten req=%.3f readback=%.3f dB"
      % (infra.get("loopback"), infra.get("tx_atten_requested_db", 0.0),
         infra.get("tx_atten_readback_db", 0.0)))
    a("    restore_result=%s" % infra.get("restore_result", "UNKNOWN"))
    if infra.get("error"):
        a("    error=%s" % infra["error"])
    for rl in rec.get("rf_leakage", []):
        a("    RF_LEAKAGE_NOT_PROVEN file=%s atten(%.3f/%.3f dB) loopback=%d "
          "antenna=%s coax=%s ensm=%s"
          % (rl["file"], rl["tx_atten_requested_db"], rl["tx_atten_readback_db"],
             rl["loopback"], rl["antenna"], rl["coax"], rl["ensm"]))

    a("")
    a("[2] FIDELITY (observation-only; NMSE/EVM/CFO/correlation per file)")
    for pf in rec["files"]:
        fid = pf.get("fidelity")
        if fid:
            a("    %-32s %-36s nmse=%.6f evm=%.3f%% corr=%.6f cfo=%+.3f Hz "
              "delay=%d gain=%.3f dB phase=%.3f deg"
              % (pf["file"], fid["verdict"], fid["nmse"], fid["evm_pct"],
                 fid["corr"], fid["cfo_hz"], fid["delay"], fid["gain_db"],
                 fid["phase_deg"]))
        else:
            a("    %-32s %s" % (pf["file"],
                                pf.get("classification_error", "INSUFFICIENT_EVIDENCE")))

    a("")
    a("[3] CLASSIFICATION (measurement-only; never an accuracy gate)")
    for ik, k in sorted(rec["input_kinds"].items()):
        rr = ("%.4f" % k["recovered_rate"]) if k["recovered_rate"] is not None else "n/a"
        fr = ("%.4f" % k["frozen_rate"]) if k["frozen_rate"] is not None else "n/a"
        a("    input_kind=%-32s verdict=%-40s frames=%d correct=%d "
          "recovered_rate=%s frozen_rate=%s has_frozen_ref=%s"
          % (ik, k["verdict"], k["frames"], k["correct"], rr, fr,
             k["has_frozen_ref"]))

    if "frozen_verify" in rec:
        fv = rec["frozen_verify"]
        a("")
        a("[4] FROZEN ARTIFACT RE-VERIFY (manifest=%s) all_ok=%s"
          % (fv.get("manifest"), fv.get("all_ok")))
        if fv.get("error"):
            a("    error=%s" % fv["error"])
        for f in fv.get("files", []):
            a("    %-40s ok=%s size=%s sha256=%s%s"
              % (f["file"], f["ok"], f.get("size", "-"), f.get("sha256", "-"),
                 (" " + f["error"]) if f.get("error") else ""))

    a("")
    a("Verdicts are SEPARATE: a classification error does NOT fail infrastructure "
      "and vice versa (Stage H-E requirement 11).  arbitrary_modulated_iq_fidelity "
      "is only ever BOARD_REQUIRED here; PRESERVES/DISTORTS is only set by a board run.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", action="append", default=[],
                    help="board producer stdout (repeatable, or a directory)")
    ap.add_argument("--frozen-dir", default=None)
    ap.add_argument("--input-kind", default=None,
                    help="generated-2p56m|radioml-reconstructed-2p56m")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    if not args.log:
        ap.error("--log is required (the board's Route E producer stdout)")

    rec = analyze(args.log, args.frozen_dir, args.input_kind)
    print(render(rec))

    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rec, f, indent=2, sort_keys=True)
        print("wrote %s" % args.json)


if __name__ == "__main__":
    main()
