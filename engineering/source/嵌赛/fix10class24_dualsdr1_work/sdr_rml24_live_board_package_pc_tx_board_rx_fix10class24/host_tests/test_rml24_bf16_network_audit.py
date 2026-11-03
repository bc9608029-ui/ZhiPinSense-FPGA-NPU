#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_rml24_bf16_network_audit.py -- pure-stdlib unittest of the BF16 network audit.

fix10class24-dualsdr1 §5 (Phase 0): the frozen full-network BF16 model must audit to
1 Input + 122 HardOp + 1 Output, 122 ops -> @zhuget(330) NPU + 2 -> @hostt, ZERO int8
storage, input [1,2,1024]/output [1,24] fp32, and DEPLOYABLE_FULL_NETWORK_BF16.  This
loads the SAME audit script the operator runs, by absolute path, runs it against a
COPY of model_rml24_bf16/ in a temp dir (so it never mutates the tree), and asserts the
regenerated report's deployability verdict + census.  Pure stdlib, no icraft.
"""

import importlib.util
import json
import os
import shutil
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_TREE = os.path.normpath(os.path.join(_HERE, ".."))
_MOD_PATH = os.path.normpath(os.path.join(_TREE, "scripts",
                                          "audit_rml24_bf16_network.py"))
_MODEL_DIR = os.path.normpath(os.path.join(_TREE, "model_rml24_bf16"))

_spec = importlib.util.spec_from_file_location("audit_rml24_bf16_network", _MOD_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load audit_rml24_bf16_network.py at %s" % _MOD_PATH)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

_MODEL_FILES = ("rml24_adamrv11_bf16.json", "rml24_adamrv11_bf16.raw",
                "model_SHA256SUMS.txt")


class TestBf16NetworkAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rml24_audit_")
        for f in _MODEL_FILES:
            shutil.copy2(os.path.join(_MODEL_DIR, f), os.path.join(self.tmp, f))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_audit_passes_and_regenerates_report(self):
        rc = audit.main(["--model-dir", self.tmp])
        self.assertEqual(rc, 0)
        report_path = os.path.join(self.tmp, "network_mapping_report.json")
        self.assertTrue(os.path.isfile(report_path))
        with open(report_path, encoding="utf-8") as fh:
            r = json.load(fh)

        self.assertEqual(r["op_inventory"]["input"], 1)
        self.assertEqual(r["op_inventory"]["hard_op"], 122)
        self.assertEqual(r["op_inventory"]["output"], 1)
        self.assertEqual(r["npu_resident_ops"], 122)
        self.assertEqual(r["host_ops"], 2)
        self.assertEqual(r["int8_tensors"], 0)
        self.assertEqual(r["deployability"]["verdict"],
                         "DEPLOYABLE_FULL_NETWORK_BF16")
        self.assertEqual(r["network_io"]["input_shape"], [1, 2, 1024])
        self.assertEqual(r["network_io"]["output_shape"], [1, 24])
        self.assertEqual(r["network_io"]["input_dtype"], "fp32")
        self.assertEqual(r["network_io"]["output_dtype"], "fp32")
        self.assertEqual(r["model_json_sha256"], audit.FROZEN["json_sha256"])
        self.assertEqual(r["model_raw_sha256"], audit.FROZEN["raw_sha256"])
        self.assertGreater(r["activation_values"]["unique_count"], 0)

    def test_frozen_constants_consistent(self):
        # The frozen SHA constants must match the on-disk model bytes (the audit
        # already enforces this; re-check here as a belt-and-braces sanity).
        for f, key in (("rml24_adamrv11_bf16.json", "json_sha256"),
                       ("rml24_adamrv11_bf16.raw", "raw_sha256")):
            got = audit.sha256_file(os.path.join(self.tmp, f))
            self.assertEqual(got, audit.FROZEN[key])

    def test_missing_raw_fails_closed(self):
        os.unlink(os.path.join(self.tmp, "rml24_adamrv11_bf16.raw"))
        # main()'s fail() path calls sys.exit(1) (the CLI contract), so the
        # fail-closed behaviour surfaces as a non-zero SystemExit, not a return.
        with self.assertRaises(SystemExit) as ctx:
            audit.main(["--model-dir", self.tmp])
        self.assertNotEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
