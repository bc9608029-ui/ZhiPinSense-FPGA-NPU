#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix10_burst_cache.py -- pure-stdlib burst cache (iio-free, subprocess-free).

fix10prep3 §4.2: PREPARE must never launch WSL/g++ inside the 2-second message window.
The burst for each (frozen ci16, complex_count, payload_sha_pre, target_rms) is built
ONCE ahead of time (prewarm, before listen) and PREPARE only READS the cache.  This
module holds the cache key + cache + the pure cache-only lookup, so it can be
unit-tested under any Python 3 with no libiio and no subprocess.

Key contract: burst_cache_key() must be deterministic, and it must incorporate the
exact target_rms (via %.17g, which round-trips the double), because prewarm uses the
CLI --rf-tx-target-rms while PREPARE uses HELLO's target_rms; a mismatch yields a cache
miss -- which is the CORRECT fail-closed behavior, not a bug.
"""

import os

__all__ = ["BurstCache", "BurstCacheMiss", "burst_cache_key", "require_cached_burst"]


def burst_cache_key(ci16_path, complex_count, expect_sha, target_rms):
    """Deterministic cache key: (abspath, int, sha, "%.17g" % rms)."""
    return (os.path.abspath(ci16_path), int(complex_count),
            str(expect_sha), "%.17g" % float(target_rms))


class BurstCacheMiss(Exception):
    """A required burst is absent from the cache (fail-closed PREPARE)."""


class BurstCache:
    """A minimal in-memory key -> (burst_bytes, prov) store."""

    def __init__(self):
        self._data = {}

    def get(self, key):
        return self._data.get(key)

    def put(self, key, value):
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data

    def __len__(self):
        return len(self._data)


def require_cached_burst(cache, key, source_index):
    """Pure cache-only lookup: hit -> (burst_bytes, prov); miss -> BurstCacheMiss.

    Contains NO subprocess / iio / filesystem / Windows dependency -- this is the exact
    function PREPARE runs, so testing it directly proves PREPARE can never launch
    WSL/g++.
    """
    hit = cache.get(key)
    if hit is None:
        raise BurstCacheMiss("BURST_CACHE_MISS source_index=%d" % source_index)
    return hit
