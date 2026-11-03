#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_rml24_prewarm_plan.py -- pure-stdlib unittest of build_rml24_prewarm_plan.py.

fix10class24-dualsdr1 §14: the PC-side 24-sample prewarm plan must be deterministic
(two runs -> byte-identical), fail-closed on a corrupted manifest / missing or
wrong-SHA CI16, and carry the exact source_index/file_name/complex_count/
quantized_sha256/target_rms identity the PC prewarm + PREPARE both check against.
This loads the SAME script the operator runs, by absolute path, against the FROZEN
clean24_smoke assets, so it exercises the exact production code path without libiio
or subprocess.
"""

import importlib.util
import os
import shutil
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_TREE = os.path.normpath(os.path.join(_HERE, ".."))
_MOD_PATH = os.path.normpath(os.path.join(_TREE, "scripts",
                                          "build_rml24_prewarm_plan.py"))
_FROZEN_DIR = os.path.normpath(os.path.join(_TREE, "clean24_smoke"))

_spec = importlib.util.spec_from_file_location("build_rml24_prewarm_plan", _MOD_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load build_rml24_prewarm_plan.py at %s" % _MOD_PATH)
plan_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plan_mod)


class TestPreWarmPlan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rml24_prewarm_")
        self.out = os.path.join(self.tmp, "plan")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_plan_success_and_shape(self):
        rc = plan_mod.main(["--frozen-dir", _FROZEN_DIR, "--out-dir", self.out,
                            "--target-rms", "2048"])
        self.assertEqual(rc, 0)
        tsv = os.path.join(self.out, "rml24_prewarm_plan.tsv")
        self.assertTrue(os.path.isfile(tsv))
        lines = open(tsv, encoding="utf-8").read().splitlines()
        self.assertEqual(lines[0], plan_mod.PLAN_HEADER)
        rows = lines[1:]
        self.assertEqual(len(rows), 24)
        src = []
        for r in rows:
            p = r.split("\t")
            self.assertEqual(len(p), 5)
            src.append(int(p[0]))
            self.assertEqual(int(p[2]), 53760)
            self.assertTrue(plan_mod.is_hex64(p[3]))
            self.assertEqual(p[4], "2048")
        self.assertEqual(src, list(range(0, 11500 + 1, 500)))

    def test_deterministic_two_runs(self):
        out1 = os.path.join(self.tmp, "p1")
        out2 = os.path.join(self.tmp, "p2")
        self.assertEqual(plan_mod.main(["--frozen-dir", _FROZEN_DIR, "--out-dir", out1]), 0)
        self.assertEqual(plan_mod.main(["--frozen-dir", _FROZEN_DIR, "--out-dir", out2]), 0)
        a = open(os.path.join(out1, "rml24_prewarm_plan.tsv"), "rb").read()
        b = open(os.path.join(out2, "rml24_prewarm_plan.tsv"), "rb").read()
        self.assertEqual(a, b)
        ja = open(os.path.join(out1, "rml24_prewarm_plan.json"), "rb").read()
        jb = open(os.path.join(out2, "rml24_prewarm_plan.json"), "rb").read()
        self.assertEqual(ja, jb)

    def test_json_summary(self):
        self.assertEqual(plan_mod.main(["--frozen-dir", _FROZEN_DIR, "--out-dir", self.out]), 0)
        import json
        with open(os.path.join(self.out, "rml24_prewarm_plan.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual(s["sample_count"], 24)
        self.assertEqual(s["source_index_min"], 0)
        self.assertEqual(s["source_index_max"], 11500)
        self.assertEqual(s["source_index_step"], 500)
        self.assertTrue(s["all_holdout"])
        self.assertEqual(s["ci16_sha_verified"], 24)

    def test_missing_manifest_fails_closed(self):
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        rc = plan_mod.main(["--frozen-dir", empty, "--out-dir", self.out])
        self.assertNotEqual(rc, 0)

    def test_corrupt_sha_fails_closed(self):
        # Copy the frozen dir, then flip one byte of one CI16 -> sha mismatch.
        corrupt = os.path.join(self.tmp, "corrupt")
        shutil.copytree(_FROZEN_DIR, corrupt)
        target = os.path.join(corrupt, "clean_ook_210e585d.ci16")
        with open(target, "r+b") as fh:
            fh.seek(0)
            b = fh.read(1)
            fh.seek(0)
            fh.write(bytes([(b[0] ^ 0xFF)]))
        rc = plan_mod.main(["--frozen-dir", corrupt, "--out-dir", self.out])
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
