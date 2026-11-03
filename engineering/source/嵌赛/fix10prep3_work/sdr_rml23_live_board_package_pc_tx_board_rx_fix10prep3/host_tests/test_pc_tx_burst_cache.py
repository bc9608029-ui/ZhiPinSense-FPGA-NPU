#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_pc_tx_burst_cache.py -- pure-stdlib unittest of fix10_burst_cache.py.

fix10prep3 §4.2: PREPARE must never launch WSL/g++ inside the 2-second window, so the
burst is built once ahead of time (prewarm) and PREPARE only reads the cache via the
pure function require_cached_burst().  This test loads the SAME package module
pc_tx_sdr_fix10.py loads and directly exercises the exact production lookup, proving it
is deterministic, keyed on target_rms, and fails closed on a miss -- all without libiio
or subprocess.
"""

import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD_PATH = os.path.normpath(os.path.join(_HERE, "..", "host_tools",
                                          "fix10_burst_cache.py"))

_spec = importlib.util.spec_from_file_location("fix10_burst_cache", _MOD_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load fix10_burst_cache.py at %s" % _MOD_PATH)
burst_cache = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(burst_cache)


class TestBurstCacheKey(unittest.TestCase):
    def test_deterministic(self):
        a = burst_cache.burst_cache_key("/mnt/f/x.ci16", 53760, "a" * 64, 2048.0)
        b = burst_cache.burst_cache_key("/mnt/f/x.ci16", 53760, "a" * 64, 2048.0)
        self.assertEqual(a, b)

    def test_rms_roundtrip_stable(self):
        # 2048.0 and 2048 must produce the same key (%.17g round-trips the double).
        a = burst_cache.burst_cache_key("/x.ci16", 1, "a" * 64, 2048.0)
        b = burst_cache.burst_cache_key("/x.ci16", 1, "a" * 64, 2048)
        self.assertEqual(a, b)

    def test_path_changes_key(self):
        a = burst_cache.burst_cache_key("/a.ci16", 1, "a" * 64, 2048.0)
        b = burst_cache.burst_cache_key("/b.ci16", 1, "a" * 64, 2048.0)
        self.assertNotEqual(a, b)

    def test_sha_changes_key(self):
        a = burst_cache.burst_cache_key("/x.ci16", 1, "a" * 64, 2048.0)
        b = burst_cache.burst_cache_key("/x.ci16", 1, "b" * 64, 2048.0)
        self.assertNotEqual(a, b)

    def test_rms_changes_key(self):
        a = burst_cache.burst_cache_key("/x.ci16", 1, "a" * 64, 2048.0)
        b = burst_cache.burst_cache_key("/x.ci16", 1, "a" * 64, 2047.0)
        self.assertNotEqual(a, b)

    def test_complex_count_changes_key(self):
        a = burst_cache.burst_cache_key("/x.ci16", 53760, "a" * 64, 2048.0)
        b = burst_cache.burst_cache_key("/x.ci16", 53761, "a" * 64, 2048.0)
        self.assertNotEqual(a, b)


class TestBurstCache(unittest.TestCase):
    def test_put_get(self):
        c = burst_cache.BurstCache()
        key = burst_cache.burst_cache_key("/x.ci16", 1, "a" * 64, 2048.0)
        self.assertIsNone(c.get(key))
        c.put(key, (b"bytes", {"tx_scale": 1.0}))
        self.assertEqual(c.get(key), (b"bytes", {"tx_scale": 1.0}))
        self.assertIn(key, c)
        self.assertEqual(len(c), 1)

    def test_get_missing_is_none(self):
        c = burst_cache.BurstCache()
        key = burst_cache.burst_cache_key("/x.ci16", 1, "a" * 64, 2048.0)
        self.assertIsNone(c.get(key))


class TestRequireCachedBurst(unittest.TestCase):
    def test_hit_returns_value(self):
        c = burst_cache.BurstCache()
        key = burst_cache.burst_cache_key("/x.ci16", 53760, "a" * 64, 2048.0)
        value = (b"burst", {"burst_sha": "b" * 64})
        c.put(key, value)
        self.assertEqual(burst_cache.require_cached_burst(c, key, 405512), value)

    def test_miss_fails_closed(self):
        c = burst_cache.BurstCache()
        key = burst_cache.burst_cache_key("/x.ci16", 53760, "a" * 64, 2048.0)
        with self.assertRaises(burst_cache.BurstCacheMiss) as cm:
            burst_cache.require_cached_burst(c, key, 405512)
        self.assertIn("BURST_CACHE_MISS", str(cm.exception))
        self.assertIn("405512", str(cm.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
