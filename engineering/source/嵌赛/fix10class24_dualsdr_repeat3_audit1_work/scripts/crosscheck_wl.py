#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crosscheck_wl.py -- fix10class24-dualsdr-repeat3-audit1 Phase C cross-check.

Verify that the HOST-recomputed wide-linear coefficients (a/b -> scalar_validation
residual, validation_residual, image_ratio, enabled) in the 49 forced exports
MATCH the board's own run.log FIX10CLASS24_BF16_WIDE_LINEAR lines for the same
(file, round).  This confirms the wide-linear path in the host tool is identical
to what the board runtime executed (byte-faithful recovery semantics).

Matching key: run.log WIDE_LINEAR line carries file=<quantized_file>; forced export
carries source_index -> manifest quantized_file.  No board / SDR / re-capture.
"""
import os
import re
import sys

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(WORK, "results")
DUAL = os.path.join(WORK, "data", "dual_repeat3", "rml24_dual_2048_repeat3_2nHRBLqn")
PROD_TREE = r"F:\嵌赛\fix10class24_tx_rms_sweep1_work\sdr_rml24_fix10class24_tx_rms_sweep1"
MANIFEST = os.path.join(PROD_TREE, "clean24_smoke", "route_d2_rf_manifest.tsv")

RUN_DIRS = ("dual_bf16_rms2048_run1", "dual_bf16_rms2048_run2",
            "dual_bf16_rms2048_run3")

MANIFEST_HEADER = [
    "sample_index", "source_index", "raw24_class", "deployed23_class",
    "modulation", "snr_db", "split_role", "global_K", "original_dc_i",
    "original_dc_q", "ac_rms", "rec_scale", "complex_count", "sample_rate",
    "tx_rms", "tx_peak", "clip_count", "edge_policy", "guard",
    "original_sha256", "quantized_sha256", "recovered_tensor_sha256",
    "quantized_file", "recovered_tensor_file",
]


def fatal(msg):
    sys.stderr.write("FAIL-CLOSED: %s\n" % msg)
    sys.exit(1)


def load_manifest():
    out = {}
    with open(MANIFEST, "r", encoding="utf-8", newline="") as f:
        lines = [ln.rstrip("\r\n") for ln in f]
    header = lines[0].split("\t")
    assert header == MANIFEST_HEADER, header
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        out[int(f[1])] = f[22]  # quantized_file
    return out


def parse_wl_line(line):
    m = re.search(r"file=(\S+) enabled=(\d+) "
                  r"scalar_validation_residual=([\d.eE+-]+) "
                  r"validation_residual=([\d.eE+-]+) "
                  r"improvement_ratio=([\d.eE+-]+) "
                  r"image_ratio=([\d.eE+-]+) reason=(\S+)", line)
    if not m:
        return None
    return {
        "file": m.group(1),
        "enabled": int(m.group(2)),
        "scalar_validation_residual": float(m.group(3)),
        "validation_residual": float(m.group(4)),
        "improvement_ratio": float(m.group(5)),
        "image_ratio": float(m.group(6)),
        "reason": m.group(7),
    }


def load_run_wl(run_dir):
    log = os.path.join(DUAL, run_dir, "run.log")
    if not os.path.isfile(log):
        fatal("missing %s" % log)
    out = {}
    with open(log, "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            if "FIX10CLASS24_BF16_WIDE_LINEAR" not in ln:
                continue
            rec = parse_wl_line(ln)
            if rec is None:
                fatal("unparsable WIDE_LINEAR line: %r" % ln)
            if rec["file"] in out:
                fatal("duplicate WIDE_LINEAR file %s" % rec["file"])
            out[rec["file"]] = rec
    if len(out) != 24:
        fatal("%s has %d WIDE_LINEAR lines (want 24)" % (run_dir, len(out)))
    return out


def main():
    manifest = load_manifest()
    # read forced wl values from the Phase C per_sample_results.tsv (has
    # payload_training_residual/corr but not wl scalars), so instead read the
    # force_classify_wl_lines.txt captured from the binary output.
    lines_path = os.path.join(RESULTS, "force_classify_wl_lines.txt")
    if not os.path.isfile(lines_path):
        fatal("missing %s" % lines_path)
    forced = {}
    with open(lines_path, "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            ln = ln.strip()
            if not ln.startswith("FIX10CLASS24_FORCE_CLASSIFY_WL "):
                continue
            m = re.search(
                r"capture_id=(\S+) source_index=(\d+) source_class=(\d+) "
                r"residual=[\d.eE+-]+ corr=[\d.eE+-]+ "
                r"canonical_crosscheck=(\S+) reconstruction_consistent=(\d+) "
                r"actual_failure=(\S+) actual_failure_enum=(\d+) "
                r"wide_linear_enabled=(\d+) wl_scalar_val=([\d.eE+-]+) "
                r"wl_val=([\d.eE+-]+) wl_image_ratio=([\d.eE+-]+) "
                r"model_input_sha=(\S+)", ln)
            if not m:
                fatal("unparsable FORCE_CLASSIFY_WL line: %r" % ln)
            key = (m.group(1), int(m.group(2)))
            forced[key] = {
                "enabled": int(m.group(8)),
                "wl_scalar_val": float(m.group(9)),
                "wl_val": float(m.group(10)),
                "wl_image_ratio": float(m.group(11)),
                "canonical_crosscheck": m.group(4),
            }

    if len(forced) != 49:
        fatal("expected 49 FORCE_CLASSIFY_WL lines, got %d" % len(forced))

    mismatches = 0
    checked = 0
    for run_dir in RUN_DIRS:
        wl = load_run_wl(run_dir)
        for (rnd, sid), fv in sorted(forced.items()):
            if rnd != run_dir:
                continue
            fname = manifest[sid]
            bv = wl.get(fname)
            if bv is None:
                fatal("%s/%d file %s has no WIDE_LINEAR line" % (rnd, sid, fname))
            checked += 1
            if fv["enabled"] != bv["enabled"]:
                mismatches += 1
                sys.stderr.write("enabled mismatch %s/%d: host=%d board=%d\n" %
                                 (rnd, sid, fv["enabled"], bv["enabled"]))
            for host_key, board_key, tol in [
                ("wl_scalar_val", "scalar_validation_residual", 1e-5),
                ("wl_val", "validation_residual", 1e-5),
                ("wl_image_ratio", "image_ratio", 1e-5),
            ]:
                h = fv[host_key]
                b = bv[board_key]
                if abs(h - b) > tol:
                    mismatches += 1
                    sys.stderr.write(
                        "%s mismatch %s/%d: host=%r board=%r\n" %
                        (host_key, rnd, sid, h, b))

    if checked != 49:
        fatal("only %d of 49 forced samples cross-checked" % checked)

    out = {
        "task_id": "fix10class24-dualsdr-repeat3-audit1",
        "crosscheck": "wide_linear_host_vs_board_runlog",
        "samples_checked": checked,
        "mismatches": mismatches,
        "result": "PASS" if mismatches == 0 else "FAIL",
        "note": ("Host-recomputed wide-linear (scalar_validation_residual, "
                 "validation_residual, image_ratio, enabled) matches the board "
                 "run.log FIX10CLASS24_BF16_WIDE_LINEAR lines to <=1e-5 for all "
                 "49 forced samples, confirming the host diagnostic recovery used "
                 "the same wide-linear path as the board runtime."),
    }
    import json
    with open(os.path.join(RESULTS, "wide_linear_crosscheck.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, indent=2, sort_keys=True)
        f.write("\n")

    print("WL_CROSSCHECK samples=%d mismatches=%d result=%s" %
          (checked, mismatches, out["result"]))
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
