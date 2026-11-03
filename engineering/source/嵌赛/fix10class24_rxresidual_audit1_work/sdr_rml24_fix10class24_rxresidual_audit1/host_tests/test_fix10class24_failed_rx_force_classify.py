#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Host tests for the Phase A / D / F logic of the rxresidual-audit1 Python script
(scripts/audit_fix10class24_failed_rx_forced_classification.py).

Covers, offline (no board, no icraft-run):
  Phase A  archive SHA fail-closed, safe-unpack member rejection, dirname parsing,
           frontend parsing, nco-offset evidence, and the inventory fail-closed paths
           (missing file / raw_rx SHA mismatch / JSON missing field / wrong round count /
           source_index-set mismatch).
  Phase D  raw24_logits.tsv keeps the full 24-class structure (no 24->23 merge), and the
           per-capture determinism columns are reported separately.
  Phase F  threshold recompute keeps 0.10 unchanged and never oversteps to a global
           production threshold (conclusion is capped at EVIDENCE_SUPPORTS...).

The Phase D/F tests read the committed results under ../results/rxresidual_audit when
present; Phase A builds an in-memory synthetic capture tree (tempdir) so it runs with no
board dump at all.
"""
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(_HERE, "..", "scripts")
_RESULTS = os.path.join(_HERE, "..", "results", "rxresidual_audit")
sys.path.insert(0, _SCRIPTS)

import audit_fix10class24_failed_rx_forced_classification as audit  # noqa: E402

g_pass = 0
g_fail = 0


def check(ok, what):
    global g_pass, g_fail
    if ok:
        g_pass += 1
    else:
        g_fail += 1
        print("  FAIL: %s" % what)


def assert_fail_closed(fn, substr):
    """Run fn(); expect SystemExit(1) whose stderr message contains `substr`."""
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            fn()
        check(False, "expected fail-closed, but call succeeded: %s" % substr)
    except SystemExit as e:
        check(int(e.code) == 1, "fail-closed exit code 1 for %s" % substr)
        check(substr in err.getvalue(), "fail-closed message contains %r (got %r)"
              % (substr, err.getvalue()[:200]))


# ---------------------------------------------------------------------------
# Phase A -- archive SHA fail-closed
# ---------------------------------------------------------------------------
def test_archive_sha_mismatch():
    with tempfile.TemporaryDirectory() as td:
        # A tiny valid tar.gz whose SHA != the frozen expected SHA.
        archive = os.path.join(td, "fake.tar.gz")
        import tarfile
        with tarfile.open(archive, "w:gz") as tf:
            data = b"hello"
            info = tarfile.TarInfo(name="a.txt")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        assert_fail_closed(lambda: audit.phase_extract(archive, os.path.join(td, "out")),
                           "archive SHA mismatch")


# ---------------------------------------------------------------------------
# Phase A -- safe-unpack member rejection
# ---------------------------------------------------------------------------
class _FakeMember:
    def __init__(self, name, sym=False, lnk=False):
        self.name = name
        self._sym = sym
        self._lnk = lnk

    def issym(self):
        return self._sym

    def islnk(self):
        return self._lnk


def test_is_safe_member():
    check(not audit.is_safe_member(_FakeMember("/abs/path")), "absolute path rejected")
    check(not audit.is_safe_member(_FakeMember("\\backslash")), "backslash path rejected")
    check(not audit.is_safe_member(_FakeMember("C:\\win\\path")), "drive-colon path rejected")
    check(not audit.is_safe_member(_FakeMember("../escape")), ".. traversal rejected")
    check(not audit.is_safe_member(_FakeMember("a/../../b")), "deep .. traversal rejected")
    check(not audit.is_safe_member(_FakeMember("a/b", sym=True)), "symlink rejected")
    check(not audit.is_safe_member(_FakeMember("a/b", lnk=True)), "hardlink rejected")
    check(audit.is_safe_member(_FakeMember("round/failed_rx/500/raw_rx_ci16le.bin")),
          "normal relative path accepted")


# ---------------------------------------------------------------------------
# Phase A -- dirname parsing + scalar helpers
# ---------------------------------------------------------------------------
def test_parse_capture_id_dirname():
    check(audit.parse_capture_id_dirname("rml24_rxbw_10000000_run1_1773377032") ==
          ("rxbw", 10000000, 1), "rxbw dirname parsed")
    check(audit.parse_capture_id_dirname("rml24_rxgain_45_run1_1773377950") ==
          ("rxgain", 45, 1), "rxgain dirname parsed")
    check(audit.parse_capture_id_dirname("garbage") is None, "garbage dirname -> None")
    check(audit.parse_capture_id_dirname("rml24_rxbw_abc_run1_1") is None,
          "non-numeric bw -> None")


def test_parse_bool_and_nan_json():
    check(audit.parse_bool("1") == 1 and audit.parse_bool(0) == 0, "parse_bool 1/0")
    check(audit.parse_bool("true") == 1 and audit.parse_bool("false") == 0,
          "parse_bool true/false")
    try:
        audit.parse_bool("maybe")
        check(False, "parse_bool('maybe') should raise")
    except ValueError:
        check(True, "parse_bool('maybe') raises ValueError")

    fixed = audit._fix_nan_literals('{"snr_db": nan, "x": "nan", "y": -inf}')
    check("NaN" in fixed and "-Infinity" in fixed, "_fix_nan_literals fixes nan/inf")
    check('"nan"' in fixed, "_fix_nan_literals leaves string literal untouched")


# ---------------------------------------------------------------------------
# Phase A -- frontend parsing + nco-offset evidence
# ---------------------------------------------------------------------------
def test_frontend_from_run_log():
    with tempfile.TemporaryDirectory() as td:
        good = os.path.join(td, "good.log")
        with open(good, "w") as f:
            f.write("FIX10CLASS24_BF16_RX_FRONTEND requested_rx_bw=10000000 "
                    "rx_bw_readback=10000000 requested_rx_gain=35 rx_gain_readback=35 "
                    "rx_bw_ok=1 rx_gain_ok=1\n")
        fe = audit.frontend_from_run_log(good)
        check(fe is not None and fe["requested_rx_bw"] == "10000000", "frontend parsed")
        check(fe["rx_gain_ok"] == "1", "frontend rx_gain_ok parsed")

        missing = os.path.join(td, "missing.log")
        with open(missing, "w") as f:
            f.write("FIX10CLASS24_BF16_RX_FRONTEND requested_rx_bw=10000000\n")
        assert_fail_closed(lambda: audit.frontend_from_run_log(missing),
                           "missing fields")

        absent = os.path.join(td, "absent.log")
        check(audit.frontend_from_run_log(absent) is None, "absent run.log -> None")


def test_nco_offset_evidence():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "run.log")
        with open(p, "w") as f:
            f.write("cmd --nco-offset=12.5 --other=1\n")
        val, ev = audit.nco_offset_evidence(p, os.path.join(td, "no.json"))
        check(val == 12.5 and ev == "run_log_explicit", "nco-offset explicit parsed")

        p2 = os.path.join(td, "run2.log")
        with open(p2, "w") as f:
            f.write("cmd --rx-bw 10000000\n")
        val, ev = audit.nco_offset_evidence(p2, os.path.join(td, "no.json"))
        check(val == 0.0 and ev == "production_default_and_board_command_omission",
              "nco-offset default + evidence when omitted")


# ---------------------------------------------------------------------------
# Phase A -- inventory (synthetic 15-round tree, then each fail-closed mutation)
# ---------------------------------------------------------------------------
def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _write_round(root, dname, encoded_var, encoded_val):
    """Create one round dir with failed_rx/{500,1500} and frontend params."""
    rp = os.path.join(root, dname)
    os.makedirs(rp, exist_ok=True)

    # frontend source: rxbw -> run.log, rxgain -> summary.json
    if encoded_var == "rxbw":
        with open(os.path.join(rp, "run.log"), "w") as f:
            f.write("FIX10CLASS24_BF16_RX_FRONTEND requested_rx_bw=%d rx_bw_readback=%d "
                    "requested_rx_gain=35 rx_gain_readback=35 rx_bw_ok=1 rx_gain_ok=1\n"
                    % (encoded_val, encoded_val))
    else:
        with open(os.path.join(rp,
                               "route_f_fix10class24_bf16_pc_tx_board_rx_summary.json"),
                  "w") as f:
            json.dump({
                "requested_rx_bw": 10000000, "rx_bw_readback": 10000000,
                "requested_rx_gain": encoded_val, "rx_gain_readback": encoded_val,
                "rx_bw_ok": 1, "rx_gain_ok": 1,
            }, f)

    for idx in ("500", "1500"):
        sdir = os.path.join(rp, "failed_rx", idx)
        os.makedirs(sdir, exist_ok=True)
        raw = ("raw-%s-%s" % (dname, idx)).encode()
        with open(os.path.join(sdir, "raw_rx_ci16le.bin"), "wb") as f:
            f.write(raw)
        # 6 other required files (contents don't matter for inventory)
        for name in ("expected_scaled_payload_ci16le.bin",
                     "expected_full_burst_ci16le.bin",
                     "coarse_corrected_rx_cf64le.bin",
                     "recovered_payload_f32le.bin"):
            with open(os.path.join(sdir, name), "wb") as f:
                f.write(b"\x00")
        with open(os.path.join(sdir, "SHA256SUMS.txt"), "w") as f:
            f.write("%s  raw_rx_ci16le.bin\n" % _sha(raw))
        with open(os.path.join(sdir, "recovery_diagnostics.json"), "w") as f:
            json.dump({
                "source_index": int(idx),
                "target_rms": 2048.0,
                "tx_scale": 1.0,
                "failure_enum": 3,
                "failure": "PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH",
                "payload_training_residual": 0.12,
                "payload_training_corr": 0.99,
                "timing_offset": 36074,
                "coarse_cfo_hz": -118.3,
                "fine_cfo_hz": -6.2,
                "raw_rx_sha256": _sha(raw),
                "modulation": "BPSK" if idx == "1500" else "4ASK",
                "raw24_class": 3 if idx == "1500" else 1,
            }, f)


def _full_tree(root):
    rxbw = [3000000, 5000000, 10000000, 18000000]
    for val in rxbw:
        for run in (1, 2, 3):
            _write_round(root, "rml24_rxbw_%d_run%d_1773377000" % (val, run), "rxbw", val)
    for val in (40, 45, 50):
        _write_round(root, "rml24_rxgain_%d_run1_1773377000" % val, "rxgain", val)


def test_inventory_ok_and_fail_closed():
    with tempfile.TemporaryDirectory() as td:
        root = os.path.join(td, "captures")
        out = os.path.join(td, "out")
        _full_tree(root)

        # Valid tree -> OK, 30 rows.
        rc = audit.phase_inventory(root, out)
        check(rc == 0, "inventory OK on valid 15-round tree")
        with open(os.path.join(out, "capture_inventory.tsv")) as f:
            rows = [ln for ln in f.read().splitlines() if ln]
        check(len(rows) == 31, "inventory wrote 30 data rows + header")

        # missing file -> fail-closed
        _full_tree(root)  # rebuild clean
        os.remove(os.path.join(root, "rml24_rxbw_10000000_run1_1773377000",
                               "failed_rx", "500", "raw_rx_ci16le.bin"))
        assert_fail_closed(lambda: audit.phase_inventory(root, out), "missing files")

        # raw_rx SHA mismatch -> fail-closed
        _full_tree(root)
        sdir = os.path.join(root, "rml24_rxbw_10000000_run1_1773377000", "failed_rx", "500")
        with open(os.path.join(sdir, "SHA256SUMS.txt"), "w") as f:
            f.write("deadbeef" * 8 + "  raw_rx_ci16le.bin\n")
        assert_fail_closed(lambda: audit.phase_inventory(root, out), "raw_rx SHA mismatch")

        # JSON missing field -> fail-closed
        _full_tree(root)
        jpath = os.path.join(root, "rml24_rxbw_10000000_run1_1773377000",
                             "failed_rx", "500", "recovery_diagnostics.json")
        with open(jpath) as f:
            j = json.load(f)
        del j["timing_offset"]
        with open(jpath, "w") as f:
            json.dump(j, f)
        assert_fail_closed(lambda: audit.phase_inventory(root, out), "JSON missing fields")

        # wrong round count (14) -> fail-closed
        _full_tree(root)
        import shutil
        shutil.rmtree(os.path.join(root, "rml24_rxgain_50_run1_1773377000"))
        assert_fail_closed(lambda: audit.phase_inventory(root, out), "expected 15 capture round dirs")

        # source_index-set mismatch (500 -> 501) -> fail-closed
        _full_tree(root)
        os.rename(os.path.join(root, "rml24_rxbw_10000000_run1_1773377000", "failed_rx", "500"),
                  os.path.join(root, "rml24_rxbw_10000000_run1_1773377000", "failed_rx", "501"))
        assert_fail_closed(lambda: audit.phase_inventory(root, out), "failed_rx source_index dirs")

        # extra source_index dir (501 alongside 500+1500) -> fail-closed (exactly once each)
        _full_tree(root)
        os.makedirs(os.path.join(root, "rml24_rxbw_10000000_run1_1773377000", "failed_rx", "501"),
                    exist_ok=True)
        assert_fail_closed(lambda: audit.phase_inventory(root, out), "failed_rx source_index dirs")


# ---------------------------------------------------------------------------
# Phase F -- threshold sensitivity (0.10 unchanged, no global threshold claim)
# ---------------------------------------------------------------------------
def test_threshold_0100_unchanged():
    with tempfile.TemporaryDirectory() as td:
        # synthetic per_capture_results.tsv with residuals 0.11..0.15 (all > 0.10)
        cols = ["capture_id", "source_index", "source_class", "baseline_pred", "label",
                "raw24_pred_pass1", "raw24_pred_pass2", "baseline_agreement", "label_correct",
                "finite", "repeat_argmax_deterministic", "repeat_logits_byte_identical",
                "top1_logit", "top2_logit", "margin", "payload_training_residual",
                "payload_training_corr", "raw_rx_sha256", "model_input_sha256", "result_layer"]
        lines = ["\t".join(cols)]
        for i, resid in enumerate((0.11, 0.12, 0.13, 0.14, 0.15)):
            lines.append("\t".join([
                "cap%d" % i, "1500", "3", "3", "3", "3", "3", "1", "1", "1", "1", "1",
                "1.0", "0.5", "0.5", "%.2f" % resid, "0.99", "a" * 64, "b" * 64,
                "HOST_BF16_FORCED_CLASSIFICATION",
            ]))
        with open(os.path.join(td, "per_capture_results.tsv"), "w") as f:
            f.write("\n".join(lines) + "\n")

        args = types.SimpleNamespace(out_dir=td)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = audit.phase_threshold(args)
        check(rc == 0, "phase_threshold returns 0")
        printed = out.getvalue()

        with open(os.path.join(td, "threshold_sensitivity.tsv")) as f:
            rows = [ln.split("\t") for ln in f.read().splitlines() if ln]
        header = rows[0]
        by_t = {r[0]: r for r in rows[1:]}
        check("threshold" in header and "admitted_samples" in header, "threshold TSV header")
        check(by_t["0.10"][1] == "0", "threshold 0.10 admits 0 samples (baseline unchanged)")
        check(by_t["0.16"][1] == "5", "threshold 0.16 admits all 5 samples")

        check("baseline_0100_unchanged=1" in printed, "conclusion keeps 0.10 unchanged")
        check("EVIDENCE_SUPPORTS_A_PROSPECTIVE_THRESHOLD_VALIDATION" in printed,
              "conclusion capped at EVIDENCE_SUPPORTS_A_PROSPECTIVE_THRESHOLD_VALIDATION")
        check("NEW_PRODUCTION_THRESHOLD" not in printed,
              "conclusion never claims NEW_PRODUCTION_THRESHOLD")


# ---------------------------------------------------------------------------
# Phase D -- raw24 structure (no 24->23 merge) + determinism columns split
# ---------------------------------------------------------------------------
def test_raw24_structure():
    logits_path = os.path.join(_RESULTS, "raw24_logits.tsv")
    results_path = os.path.join(_RESULTS, "per_capture_results.tsv")
    if not os.path.isfile(logits_path) or not os.path.isfile(results_path):
        print("  SKIP raw24 structure (committed results absent)")
        return

    header, rows = audit.read_tsv(logits_path)
    logit_cols = [c for c in header if c.startswith("logit_")]
    check(len(logit_cols) == 24, "raw24_logits.tsv has exactly 24 logit columns")
    check(len(rows) == 30, "raw24_logits.tsv has 30 sample rows")
    for r in rows:
        pred = int(r["raw24_pred_pass1"])
        check(0 <= pred <= 23, "raw24 pred stays in 0..23 (no 24->23 merge)")

    rheader, rrows = audit.read_tsv(results_path)
    check("repeat_argmax_deterministic" in rheader and "repeat_logits_byte_identical" in rheader,
          "per_capture_results.tsv reports determinism as two separate columns")
    check(len(rrows) == 30, "per_capture_results.tsv has 30 rows")
    sc = set(int(r["source_class"]) for r in rrows)
    check(sc == {1, 3}, "source classes are {4ASK=1, BPSK=3} (raw24, unmerged)")


def main():
    print("test_fix10class24_failed_rx_force_classify")
    tests = [
        ("archive_sha_mismatch", test_archive_sha_mismatch),
        ("is_safe_member", test_is_safe_member),
        ("parse_capture_id_dirname", test_parse_capture_id_dirname),
        ("parse_bool_and_nan_json", test_parse_bool_and_nan_json),
        ("frontend_from_run_log", test_frontend_from_run_log),
        ("nco_offset_evidence", test_nco_offset_evidence),
        ("inventory_ok_and_fail_closed", test_inventory_ok_and_fail_closed),
        ("threshold_0100_unchanged", test_threshold_0100_unchanged),
        ("raw24_structure", test_raw24_structure),
    ]
    for name, fn in tests:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            g_fail_holder = [0]
            import traceback
            traceback.print_exc()
            global g_fail
            g_fail += 1
            print("  EXCEPTION in %s: %s" % (name, e))
    print("  pass=%d fail=%d" % (g_pass, g_fail))
    return 1 if g_fail else 0


if __name__ == "__main__":
    sys.exit(main())
