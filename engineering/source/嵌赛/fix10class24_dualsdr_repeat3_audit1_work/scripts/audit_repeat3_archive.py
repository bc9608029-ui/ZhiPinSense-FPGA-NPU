#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
audit_repeat3_archive.py -- fix10class24-dualsdr-repeat3-audit1 Phase A.

Fully-offline archive/identity/inventory audit of already-captured data.  NO board,
NO SDR, NO re-capture, NO training, NO model/recovery/gate changes.

Produces (in <work>/results/):
  archive_identity.json   -- the two archive SHA256s (truncated only; archives gone)
                             + "未取得板端哈希用于比对" note.
  inventory.tsv           -- 72 rows, one per (round, source_index), from the board's
                             own per-sample results TSV + frozen manifest cross-check.
  clean_npu_audit.json    -- independently recomputed clean-NPU 24/24 (no trust of
                             GATE_RESULT; per-sample recompute).
  failed_dump_audit.json  -- per rejected sample: 7-file presence + SHA256SUMS.txt
                             recompute + failure reason (not hardcoded).

Hard gates (exit 1 on any):
  - 3 rounds each have 24 unique source_index == {0,500,...,11500} and
    raw24_class == 0..23, file_name/modulation identical to the frozen manifest.
  - every failed_rx/<idx> dump has exactly the 7 expected files and its
    SHA256SUMS.txt is internally consistent (recomputed byte hashes).
  - clean NPU is 24/24 with repeat_deterministic==24 and nan_or_inf==0.
  - no source_index is duplicated or missing within a round or across rounds.

Pure stdlib.
"""
import argparse
import hashlib
import json
import os
import sys

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- frozen production identity (tx_rms_sweep1 tree == board deploy tree) ----
PROD_TREE = r"F:\嵌赛\fix10class24_tx_rms_sweep1_work\sdr_rml24_fix10class24_tx_rms_sweep1"
MANIFEST = os.path.join(PROD_TREE, "clean24_smoke", "route_d2_rf_manifest.tsv")
BASELINE = os.path.join(PROD_TREE, "baselines", "clean24_smoke_raw24_bf16_baseline.tsv")

DATA = os.path.join(WORK, "data")
DUAL = os.path.join(DATA, "dual_repeat3", "rml24_dual_2048_repeat3_2nHRBLqn")
CLEAN_NPU = os.path.join(DATA, "clean_npu", "rml24_clean_radioml_npu_WowwwgHy")

FROZEN_MODEL_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

EXPECTED_SIDS = [i * 500 for i in range(24)]
EXPECTED_SID_SET = set(EXPECTED_SIDS)
EXPECTED_CLASSES = set(range(24))
N = 24

# archive SHA256s captured before the archives were removed; the captured output
# lines themselves were truncated (not the full 64 hex chars).  Keep both the
# 8-char prefix the task names and the longest captured prefix we actually hold.
ARCHIVE_DUAL_SHA_TRUNC = "A1FE8B2B"
ARCHIVE_CLEAN_SHA_TRUNC = "6B117052"
ARCHIVE_DUAL_SHA_CAPTURED = "A1FE8B2B075CE397978A0A0C4338E69CA107587EC30D41724EC"
ARCHIVE_CLEAN_SHA_CAPTURED = "6B117052BA971E8EC1A2241FFD0F551C573EEEFDA1AA7482"

DUAL_RESULTS = "route_f_fix10class24_bf16_pc_tx_board_rx_results.tsv"
CLEAN_RESULTS = "route_f_fix10class24_bf16_clean_iq_results.tsv"
CLEAN_SUMMARY = "route_f_fix10class24_bf16_clean_iq_summary.json"

FAILED_DUMP_FILES = [
    "raw_rx_ci16le.bin",
    "expected_scaled_payload_ci16le.bin",
    "expected_full_burst_ci16le.bin",
    "coarse_corrected_rx_cf64le.bin",
    "recovered_payload_f32le.bin",
    "recovery_diagnostics.json",
    "SHA256SUMS.txt",
]


def _fatal(msg):
    sys.stderr.write("AUDIT_FATAL: %s\n" % msg)
    sys.exit(1)


def _read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return [ln.rstrip("\r\n") for ln in f]


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json_lenient(path):
    """Board C++ dumps bare lowercase nan/inf (not strict JSON); null them out."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = (text.replace(":nan", ":null").replace(":inf", ":null")
                .replace(":-inf", ":null"))
    return json.loads(text)


def load_manifest():
    lines = _read_lines(MANIFEST)
    header = lines[0].split("\t")
    assert header[1] == "source_index" and header[2] == "raw24_class", header
    out = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        sid = int(f[1])
        cls = int(f[2])
        mod = f[4]
        fname = f[22]  # quantized_file column
        role = f[6]
        out[sid] = {"raw24_class": cls, "modulation": mod, "file_name": fname,
                    "split_role": role}
    if set(out) != EXPECTED_SID_SET:
        _fatal("manifest source_index != {0..11500 step 500}: %d rows" % len(out))
    if {v["raw24_class"] for v in out.values()} != EXPECTED_CLASSES:
        _fatal("manifest raw24_class not covering 0..23")
    return out


def load_baseline():
    lines = _read_lines(BASELINE)
    header = lines[0].split("\t")
    assert header[0] == "source_index" and header[5] == "frozen_bf16_raw24_pred", header
    out = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        sid = int(f[0])
        pred = int(f[5])
        msha = f[6]
        out[sid] = {"pred": pred, "model_sha": msha}
    if set(out) != EXPECTED_SID_SET:
        _fatal("baseline source_index != 24 rows")
    for sid, v in out.items():
        if v["model_sha"] != FROZEN_MODEL_JSON_SHA:
            _fatal("baseline source_index=%d model_sha != frozen: %s" % (sid, v["model_sha"]))
    return out


def parse_dual_results(round_dir):
    """Return list of 24 row dicts from the dual results TSV (22 cols)."""
    path = os.path.join(round_dir, DUAL_RESULTS)
    if not os.path.isfile(path):
        _fatal("missing %s" % path)
    lines = _read_lines(path)
    header = lines[0].split("\t")
    exp = ["file_name", "source_index", "raw24_class", "modulation", "snr_db",
           "split_role", "valid", "raw24_pred", "baseline_pred", "correct",
           "prediction_agreement", "repeat_deterministic", "training_corr",
           "training_residual", "timing_offset", "gain_mag", "phase_deg",
           "coarse_cfo_hz", "fine_cfo_hz", "total_cfo_hz", "sro_ppm", "rf_verdict"]
    if header != exp:
        _fatal("dual results header mismatch:\n got=%r\n exp=%r" % (header, exp))
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != 22:
            _fatal("dual results row field count != 22: %r" % ln)
        rows.append({
            "file_name": f[0], "source_index": int(f[1]), "raw24_class": int(f[2]),
            "modulation": f[3], "valid": int(f[6]), "raw24_pred": int(f[7]),
            "baseline_pred": int(f[8]), "correct": int(f[9]),
            "prediction_agreement": int(f[10]), "repeat_deterministic": int(f[11]),
            "training_corr": f[12], "training_residual": f[13],
            "rf_verdict": f[21],
        })
    return rows


def parse_clean_results():
    path = os.path.join(CLEAN_NPU, CLEAN_RESULTS)
    if not os.path.isfile(path):
        _fatal("missing %s" % path)
    lines = _read_lines(path)
    header = lines[0].split("\t")
    exp = ["file_name", "source_index", "raw24_class", "modulation", "snr_db",
           "split_role", "valid", "raw24_pred", "baseline_pred", "correct",
           "prediction_agreement", "repeat_deterministic", "window_corr",
           "window_nmse", "delay_offset", "verdict"]
    if header != exp:
        _fatal("clean results header mismatch")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != 16:
            _fatal("clean results row field count != 16")
        rows.append({
            "file_name": f[0], "source_index": int(f[1]), "raw24_class": int(f[2]),
            "modulation": f[3], "valid": int(f[6]), "raw24_pred": int(f[7]),
            "baseline_pred": int(f[8]), "correct": int(f[9]),
            "prediction_agreement": int(f[10]), "repeat_deterministic": int(f[11]),
            "verdict": f[15],
        })
    return rows


def read_config(round_dir):
    """Extract config facts from run.log (authoritative per-sample + frontend)."""
    log = os.path.join(round_dir, "run.log")
    if not os.path.isfile(log):
        _fatal("missing %s" % log)
    text = open(log, encoding="utf-8", errors="replace").read()
    facts = {}
    for key, pat in [
        ("center_hz", "center_hz="),
        ("rx_gain", "rx_gain="),
        ("rf_tx_target_rms", "rf_tx_target_rms="),
        ("requested_rx_bw", "requested_rx_bw="),
        ("input_kind", "input_kind="),
        ("frozen_dir", "frozen_dir="),
    ]:
        i = text.find(pat)
        if i >= 0:
            seg = text[i + len(pat):]
            facts[key] = seg.split()[0].rstrip(",")
    return facts


def audit_rounds(manifest, baseline):
    problems = []
    inventory_rows = []
    round_summaries = {}
    for r in (1, 2, 3):
        d = os.path.join(DUAL, "dual_bf16_rms2048_run%d" % r)
        rows = parse_dual_results(d)
        sids = [x["source_index"] for x in rows]
        if set(sids) != EXPECTED_SID_SET:
            problems.append("run%d source_index != expected set" % r)
        if len(sids) != len(set(sids)):
            problems.append("run%d has duplicate source_index" % r)
        classes = {x["raw24_class"] for x in rows}
        if classes != EXPECTED_CLASSES:
            problems.append("run%d raw24_class not covering 0..23" % r)
        for x in rows:
            m = manifest.get(x["source_index"])
            if m is None:
                problems.append("run%d sid=%d not in manifest" % (r, x["source_index"]))
                continue
            if m["file_name"] != x["file_name"]:
                problems.append("run%d sid=%d file_name mismatch %r != %r" %
                                (r, x["source_index"], x["file_name"], m["file_name"]))
            if m["modulation"] != x["modulation"]:
                problems.append("run%d sid=%d modulation mismatch" % (r, x["source_index"]))
            if m["raw24_class"] != x["raw24_class"]:
                problems.append("run%d sid=%d class mismatch" % (r, x["source_index"]))
            b = baseline[x["source_index"]]
            if x["valid"] == 1 and x["baseline_pred"] != b["pred"]:
                problems.append("run%d sid=%d baseline_pred=%d != frozen=%d" %
                                (r, x["source_index"], x["baseline_pred"], b["pred"]))
            inventory_rows.append({
                "round": r, **x,
            })
        scored = [x for x in rows if x["valid"] == 1]
        gated_correct = sum(1 for x in scored if x["correct"] == 1)
        round_summaries[r] = {
            "scored": len(scored),
            "rejected": N - len(scored),
            "gated_correct": gated_correct,
        }
        # config facts
        cfg = read_config(d)
        cfg.setdefault("center_hz", "?"), cfg.setdefault("rx_gain", "?")
        cfg.setdefault("rf_tx_target_rms", "?")
        round_summaries[r]["config"] = cfg
    return problems, inventory_rows, round_summaries


def audit_failed_dumps(inventory_rows):
    """Verify every rejected sample's 7-file dump + SHA256SUMS consistency + failure."""
    problems = []
    dump_records = []
    for r in (1, 2, 3):
        d = os.path.join(DUAL, "dual_bf16_rms2048_run%d" % r)
        rejected = [x for x in inventory_rows if x["round"] == r and x["valid"] == 0]
        for x in rejected:
            sid = x["source_index"]
            dd = os.path.join(d, "failed_rx", str(sid))
            rec = {"round": r, "source_index": sid, "modulation": x["modulation"],
                   "raw24_class": x["raw24_class"], "files_ok": True, "sha_ok": True,
                   "failure": None, "failure_enum": None, "extra_files": [], "missing": []}
            if not os.path.isdir(dd):
                problems.append("run%d failed_rx/%d missing dir" % (r, sid))
                rec["files_ok"] = False
                dump_records.append(rec)
                continue
            present = sorted(os.listdir(dd))
            for f in FAILED_DUMP_FILES:
                if f not in present:
                    rec["files_ok"] = False
                    rec["missing"].append(f)
            rec["extra_files"] = [f for f in present if f not in FAILED_DUMP_FILES]
            # failure reason from recovery_diagnostics.json (NOT hardcoded)
            jpath = os.path.join(dd, "recovery_diagnostics.json")
            if os.path.isfile(jpath):
                try:
                    j = _load_json_lenient(jpath)
                    rec["failure"] = j.get("failure")
                    rec["failure_enum"] = j.get("failure_enum")
                    rec["payload_training_residual"] = j.get("payload_training_residual")
                    rec["payload_training_corr"] = j.get("payload_training_corr")
                    rec["raw_rx_complex_count"] = j.get("raw_rx_complex_count")
                except Exception as e:
                    problems.append("run%d failed_rx/%d bad json: %s" % (r, sid, e))
            # SHA256SUMS consistency
            spath = os.path.join(dd, "SHA256SUMS.txt")
            if os.path.isfile(spath):
                try:
                    for ln in _read_lines(spath):
                        if not ln.strip():
                            continue
                        sha, name = ln.split()
                        got = _sha256_file(os.path.join(dd, name))
                        if got != sha:
                            rec["sha_ok"] = False
                            problems.append("run%d failed_rx/%d SHA mismatch %s" %
                                            (r, sid, name))
                except Exception as e:
                    rec["sha_ok"] = False
                    problems.append("run%d failed_rx/%d SHA256SUMS parse: %s" % (r, sid, e))
            else:
                rec["sha_ok"] = False
                problems.append("run%d failed_rx/%d missing SHA256SUMS.txt" % (r, sid))
            if rec["files_ok"] is False:
                problems.append("run%d failed_rx/%d missing files %s extra %s" %
                                (r, sid, rec["missing"], rec["extra_files"]))
            dump_records.append(rec)
    return problems, dump_records


def audit_clean_npu(manifest, baseline):
    problems = []
    rows = parse_clean_results()
    sids = [x["source_index"] for x in rows]
    if set(sids) != EXPECTED_SID_SET:
        problems.append("clean source_index != expected set")
    classes = {x["raw24_class"] for x in rows}
    if classes != EXPECTED_CLASSES:
        problems.append("clean raw24_class not covering 0..23")
    scored = [x for x in rows if x["verdict"] == "CLEAN_DIGITAL_SCORED"]
    excluded = [x for x in rows if x["verdict"] == "CLEAN_NO_VALID_WINDOW"]
    if len(scored) + len(excluded) != N:
        problems.append("clean scored+excluded != 24")
    for x in rows:
        m = manifest.get(x["source_index"])
        if m is None:
            problems.append("clean sid=%d not in manifest" % x["source_index"])
            continue
        if m["file_name"] != x["file_name"] or m["raw24_class"] != x["raw24_class"]:
            problems.append("clean sid=%d identity mismatch" % x["source_index"])
        if x["valid"] == 1:
            b = baseline[x["source_index"]]
            if x["baseline_pred"] != b["pred"]:
                problems.append("clean sid=%d baseline_pred mismatch" % x["source_index"])
    correct = sum(1 for x in scored if x["correct"] == 1)
    nan_or_inf = sum(1 for x in scored if x["valid"] == 0)
    repeat_det = sum(1 for x in scored if x["repeat_deterministic"] == 1)
    # summary cross-check
    sjson = json.load(open(os.path.join(CLEAN_NPU, CLEAN_SUMMARY), encoding="utf-8"))
    if sjson.get("model_sha") != FROZEN_MODEL_RAW_SHA:
        problems.append("clean summary model_sha != frozen raw")
    if sjson.get("scored") != len(scored) or sjson.get("excluded") != len(excluded):
        problems.append("clean summary scored/excluded mismatch")
    audit = {
        "scored": len(scored), "excluded": len(excluded), "correct": correct,
        "nan_or_inf": nan_or_inf, "repeat_deterministic": repeat_det,
        "label_accuracy": correct / N if N else 0.0,
        "model_sha": sjson.get("model_sha"),
        "errors": [{"source_index": x["source_index"], "raw24_class": x["raw24_class"],
                    "raw24_pred": x["raw24_pred"]} for x in scored if x["correct"] == 0],
    }
    return problems, audit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=WORK)
    args = ap.parse_args()
    results_dir = os.path.join(args.work, "results")
    os.makedirs(results_dir, exist_ok=True)

    manifest = load_manifest()
    baseline = load_baseline()

    problems, inventory_rows, round_summaries = audit_rounds(manifest, baseline)
    fp, dump_records = audit_failed_dumps(inventory_rows)
    problems += fp
    cp, clean_audit = audit_clean_npu(manifest, baseline)
    problems += cp

    # ---- archive identity ----
    archive_identity = {
        "archives_on_disk": False,
        "dual_repeat3_archive_sha256_truncated": ARCHIVE_DUAL_SHA_TRUNC,
        "clean_npu_archive_sha256_truncated": ARCHIVE_CLEAN_SHA_TRUNC,
        "dual_repeat3_archive_sha256_captured_prefix": ARCHIVE_DUAL_SHA_CAPTURED,
        "clean_npu_archive_sha256_captured_prefix": ARCHIVE_CLEAN_SHA_CAPTURED,
        "note": ("归档文件已不在本机；仅记录截断 SHA256 前缀（当时捕获的 Hash 行本身即被截断，"
                 "非完整 64 位十六进制），无法逐字节比对归档完整性。"
                 "本任务未取得板端原始 SHA256 用于两端哈希比对，故不声称已完成两端一致性核验。"),
        "board_hash_comparison_claimed": False,
        "frozen_model_json_sha": FROZEN_MODEL_JSON_SHA,
        "frozen_model_raw_sha": FROZEN_MODEL_RAW_SHA,
        "frozen_manifest": MANIFEST,
        "frozen_baseline": BASELINE,
    }

    # ---- inventory.tsv ----
    inv_path = os.path.join(results_dir, "inventory.tsv")
    inv_header = ["round", "source_index", "raw24_class", "modulation", "file_name",
                  "valid", "raw24_pred", "baseline_pred", "correct",
                  "prediction_agreement", "repeat_deterministic", "training_corr",
                  "training_residual", "rf_verdict"]
    with open(inv_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(inv_header) + "\n")
        for x in sorted(inventory_rows, key=lambda z: (z["round"], z["source_index"])):
            f.write("\t".join(str(x[h]) for h in inv_header) + "\n")

    # ---- clean_npu_audit.json ----
    with open(os.path.join(results_dir, "clean_npu_audit.json"), "w", encoding="utf-8") as f:
        json.dump(clean_audit, f, indent=2, ensure_ascii=False)

    # ---- archive_identity.json ----
    with open(os.path.join(results_dir, "archive_identity.json"), "w", encoding="utf-8") as f:
        json.dump(archive_identity, f, indent=2, ensure_ascii=False)

    # ---- failed_dump_audit.json ----
    with open(os.path.join(results_dir, "failed_dump_audit.json"), "w", encoding="utf-8") as f:
        json.dump(dump_records, f, indent=2, ensure_ascii=False)

    # ---- report ----
    print("=" * 72)
    print("fix10class24-dualsdr-repeat3-audit1 Phase A")
    print("=" * 72)
    for r in (1, 2, 3):
        s = round_summaries[r]
        print("run%d: scored=%d rejected=%d gated_correct=%d  cfg=%s" %
              (r, s["scored"], s["rejected"], s["gated_correct"], s["config"]))
    total_scored = sum(round_summaries[r]["scored"] for r in (1, 2, 3))
    total_rejected = sum(round_summaries[r]["rejected"] for r in (1, 2, 3))
    total_correct = sum(round_summaries[r]["gated_correct"] for r in (1, 2, 3))
    print("TOTAL: scored=%d rejected=%d gated_correct=%d" %
          (total_scored, total_rejected, total_correct))
    print("clean NPU: scored=%d correct=%d/24 repeat_det=%d nan_or_inf=%d" %
          (clean_audit["scored"], clean_audit["correct"],
           clean_audit["repeat_deterministic"], clean_audit["nan_or_inf"]))
    print("failed dumps audited: %d" % len(dump_records))
    failure_counts = {}
    for rec in dump_records:
        failure_counts[rec["failure"]] = failure_counts.get(rec["failure"], 0) + 1
    print("failure reasons: %s" % failure_counts)

    if problems:
        print("-" * 72)
        print("HARD GATE FAILURES (%d):" % len(problems))
        for p in problems:
            print("  - %s" % p)
        _fatal("Phase A hard gates not all passed")
    print("-" * 72)
    print("Phase A PASS: 3 rounds + failed dumps + clean NPU all verified.")
    sys.exit(0)


if __name__ == "__main__":
    main()
