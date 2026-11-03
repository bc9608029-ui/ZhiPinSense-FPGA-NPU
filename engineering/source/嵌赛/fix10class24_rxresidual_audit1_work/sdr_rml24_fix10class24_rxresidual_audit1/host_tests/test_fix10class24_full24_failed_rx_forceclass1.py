#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Host tests for the Phase A logic of the full24-failed-rx-forceclass1 audit script
(scripts/audit_fix10class24_full24_failed_rx_forceclass1.py).

Covers, offline (no board, no icraft-run):
  Phase A  safe-unpack member rejection (path traversal / absolute / link),
           archive SHA fail-closed, and the flat-20-source_index inventory fail-closed paths
           (wrong source_index set / extra dir / missing file / raw_rx SHA mismatch /
           JSON missing field / modulation mismatch).

This matches the plain check()/main() convention of
test_fix10class24_failed_rx_force_classify.py so it runs under `python3 ./<this>.py`
in run_tests.sh (WSL python3 has numpy but not pytest).
"""
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(_HERE, "..", "scripts")
sys.path.insert(0, _SCRIPTS)

import audit_fix10class24_full24_failed_rx_forceclass1 as audit  # noqa: E402

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
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            fn()
        check(False, "expected fail-closed, but call succeeded: %s" % substr)
    except SystemExit as e:
        check(int(e.code) == 1, "fail-closed exit code 1 for %s" % substr)
        check(substr in err.getvalue(), "fail-closed message contains %r (got %r)"
              % (substr, err.getvalue()[:200]))


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# 纯逻辑：安全解包成员
# ---------------------------------------------------------------------------
class _Member:
    def __init__(self, name, sym=False, lnk=False):
        self.name = name
        self._sym = sym
        self._lnk = lnk

    def issym(self):
        return self._sym

    def islnk(self):
        return self._lnk


def test_is_safe_member():
    check(audit.is_safe_member(_Member("failed_rx/9000/raw.bin")), "plain relative member safe")
    check(not audit.is_safe_member(_Member("/abs/path")), "absolute member rejected")
    check(not audit.is_safe_member(_Member("C:/x")), "drive-absolute member rejected")
    check(not audit.is_safe_member(_Member("../escape")), "parent traversal rejected")
    check(not audit.is_safe_member(_Member("failed_rx/../../etc")), "nested traversal rejected")
    check(not audit.is_safe_member(_Member("a", sym=True)), "symlink member rejected")
    check(not audit.is_safe_member(_Member("a", lnk=True)), "hardlink member rejected")


def test_extract_rejects_path_traversal_member():
    check(not audit.is_safe_member(_Member("../evil")), "../evil member rejected")
    check(not audit.is_safe_member(_Member("failed_rx/../../evil")), "nested ../ member rejected")


# ---------------------------------------------------------------------------
# 合成 20 source_index 平铺树
# ---------------------------------------------------------------------------
def _manifest_lines():
    header = "\t".join(audit.MANIFEST_HEADER)
    lines = [header]
    for k in range(24):
        sid = k * 500
        row = [
            str(k), str(sid), str(k), str(k if k < 17 else 17), "M%d" % k, "nan",
            "holdout", "2048", "0", "0", "1", "1", "53760", "2560000", "893", "2613",
            "0", "zero", "832", "0" * 64, "1" * 64, "2" * 64, "x.ci16", "rt.f32",
            "2.29", str(k), str(k if k < 17 else 17),
        ]
        lines.append("\t".join(row))
    return "\n".join(lines) + "\n"


def _json(sid):
    return {
        "source_index": sid,
        "modulation": "M%d" % (sid // 500),
        "raw24_class": sid // 500,
        "failure": "PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH",
        "failure_enum": 10,
        "target_rms": 2048,
        "tx_scale": 2.29,
        "payload_training_residual": 0.12,
        "payload_training_corr": 0.99,
        "timing_offset": 50000,
        "coarse_cfo_hz": -100.0,
        "fine_cfo_hz": 0.3,
        "raw_rx_sha256": None,
    }


def _full_tree(root):
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "manifest.tsv"), "w", encoding="utf-8") as f:
        f.write(_manifest_lines())
    fd = os.path.join(root, "failed_rx")
    os.makedirs(fd, exist_ok=True)
    for sid in audit.EXPECT_SOURCE_INDEXES:
        d = os.path.join(fd, str(sid))
        os.makedirs(d, exist_ok=True)
        raw = ("raw-%d" % sid).encode() * 8
        j = _json(sid)
        j["raw_rx_sha256"] = sha(raw)
        for name in audit.REQUIRED_FILES:
            p = os.path.join(d, name)
            if name == "raw_rx_ci16le.bin":
                with open(p, "wb") as f:
                    f.write(raw)
            elif name == "recovery_diagnostics.json":
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(j, f)
            elif name == "SHA256SUMS.txt":
                with open(p, "w", encoding="utf-8") as f:
                    f.write("%s  raw_rx_ci16le.bin\n" % sha(raw))
            else:
                with open(p, "wb") as f:
                    f.write(b"x")


def _out(root):
    return os.path.join(root, "out")


def test_inventory_ok():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td)
        audit.phase_inventory(td, os.path.join(td, "manifest.tsv"), _out(td))
        check(os.path.isfile(os.path.join(_out(td), "inventory.tsv")),
              "inventory.tsv written on valid tree")


def test_inventory_wrong_archive_source_set():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td)
        os.rename(os.path.join(td, "failed_rx", "500"), os.path.join(td, "failed_rx", "501"))
        assert_fail_closed(
            lambda: audit.phase_inventory(td, os.path.join(td, "manifest.tsv"), _out(td)),
            "source_index")


def test_inventory_extra_dir():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td)
        os.makedirs(os.path.join(td, "failed_rx", "501"), exist_ok=True)
        assert_fail_closed(
            lambda: audit.phase_inventory(td, os.path.join(td, "manifest.tsv"), _out(td)),
            "source_index")


def test_inventory_missing_file():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td)
        os.remove(os.path.join(td, "failed_rx", "1500", "coarse_corrected_rx_cf64le.bin"))
        assert_fail_closed(
            lambda: audit.phase_inventory(td, os.path.join(td, "manifest.tsv"), _out(td)),
            "missing")


def test_inventory_raw_sha_mismatch():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td)
        p = os.path.join(td, "failed_rx", "1500", "raw_rx_ci16le.bin")
        with open(p, "wb") as f:
            f.write(b"tampered")
        assert_fail_closed(
            lambda: audit.phase_inventory(td, os.path.join(td, "manifest.tsv"), _out(td)),
            "SHA")


def test_inventory_json_missing_field():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td)
        p = os.path.join(td, "failed_rx", "1500", "recovery_diagnostics.json")
        j = json.load(open(p, encoding="utf-8"))
        del j["fine_cfo_hz"]
        json.dump(j, open(p, "w", encoding="utf-8"))
        assert_fail_closed(
            lambda: audit.phase_inventory(td, os.path.join(td, "manifest.tsv"), _out(td)),
            "fine_cfo_hz")


def test_inventory_modulation_mismatch():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td)
        p = os.path.join(td, "failed_rx", "1500", "recovery_diagnostics.json")
        j = json.load(open(p, encoding="utf-8"))
        j["modulation"] = "WRONG"
        json.dump(j, open(p, "w", encoding="utf-8"))
        assert_fail_closed(
            lambda: audit.phase_inventory(td, os.path.join(td, "manifest.tsv"), _out(td)),
            "modulation")


def test_extract_rejects_wrong_sha():
    with tempfile.TemporaryDirectory() as td:
        bad = os.path.join(td, "bad.tar.gz")
        with open(bad, "wb") as f:
            f.write(b"not a real archive")
        assert_fail_closed(
            lambda: audit.phase_extract(bad, os.path.join(td, "dest")),
            "archive SHA mismatch")


def main():
    tests = [
        ("is_safe_member", test_is_safe_member),
        ("extract_rejects_path_traversal_member", test_extract_rejects_path_traversal_member),
        ("inventory_ok", test_inventory_ok),
        ("inventory_wrong_archive_source_set", test_inventory_wrong_archive_source_set),
        ("inventory_extra_dir", test_inventory_extra_dir),
        ("inventory_missing_file", test_inventory_missing_file),
        ("inventory_raw_sha_mismatch", test_inventory_raw_sha_mismatch),
        ("inventory_json_missing_field", test_inventory_json_missing_field),
        ("inventory_modulation_mismatch", test_inventory_modulation_mismatch),
        ("extract_rejects_wrong_sha", test_extract_rejects_wrong_sha),
    ]
    for name, fn in tests:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            global g_fail
            g_fail += 1
            print("  EXCEPTION in %s: %s" % (name, e))
    print("  pass=%d fail=%d" % (g_pass, g_fail))
    return 1 if g_fail else 0


if __name__ == "__main__":
    sys.exit(main())
