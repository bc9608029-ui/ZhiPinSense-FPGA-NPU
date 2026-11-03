#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_pc_tx_simulated_device.py -- G4 acceptance: simulated-device control-flow test
for the public-protocol PC TX service (fix1 v1 AND fix1v2 v2).

What it proves (no libiio, no RF, plain `python -I`):
  1. the PC TX server speaks the frozen HELLO -> HELLO_ACK -> PREPARE -> PREPARED ->
     START -> READY -> CAPTURED -> STOPPED cycle over 127.0.0.1 for ALL 24 frames,
     for BOTH frozen conversions (v1 and v2);
  2. the provenance contract the board asserts is produced byte-exactly:
     payload_sha_pre == payload_sha_post == burst_sha == manifest burst_sha256,
     tx_scale == 1.0 (the public burst is pre-scaled to S, so the PC never re-scales),
     tx_running == true on READY, tx_restore_ok == true on STOPPED;
  3. the manifest SHA-256 binding (the board's session manifest_sha256) matches the
     frozen constants, and every burst file's SHA matches its manifest row;
  4. fail-closed rejection: a wrong manifest_sha256 in HELLO and a wrong
     payload_sha_pre in PREPARE are refused, not silently accepted.

Run:
    D:\\Anaconda\\python.exe -I host_tests\\test_pc_tx_simulated_device.py ^
        --v1 <fix10class24_independent_rx_delivery_fix1_work\\tx_package> ^
        --v2 <fix10class24_waveform_correct_v2_work\\tx_package>
"""

import argparse
import hashlib
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.normpath(os.path.join(_HERE, "..", "host_tools"))

# Frozen manifest SHA-256 constants (byte SHA of public_protocol_tx_manifest.tsv).
FROZEN_MANIFEST_SHA_V1 = "a1b6c9da10e62c1f4297a6d9ab797e4e6deadff04b5ed8cf3df382a18e659ef5"
FROZEN_MANIFEST_SHA_V2 = "45c493f04bbe3bfd0194810b8a7717cf765916a4e8baaad172e31e5d30ca8847"

V1_DEFAULT = r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\tx_package"
V2_DEFAULT = r"F:\嵌赛\fix10class24_waveform_correct_v2_work\tx_package"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot locate %s" % path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pc = _load_module("pc_tx_sdr_fix10_public", os.path.join(_TOOLS, "pc_tx_sdr_fix10_public.py"))


def log(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def main(argv):
    p = argparse.ArgumentParser(prog="test_pc_tx_simulated_device.py")
    p.add_argument("--v1", default=V1_DEFAULT)
    p.add_argument("--v2", default=V2_DEFAULT)
    args = p.parse_args(argv)

    g_pass = 0
    g_fail = 0

    def check(name, ok, detail=""):
        nonlocal g_pass, g_fail
        if ok:
            g_pass += 1
            log("  PASS  %-52s %s" % (name, detail))
        else:
            g_fail += 1
            log("  FAIL  %-52s %s" % (name, detail))

    log("== R1 TX-restore counterexamples (injected fake-iio device) ==")
    _run_restore_counterexamples(check)

    for label, frozen_dir, frozen_sha in (
            ("v1", args.v1, FROZEN_MANIFEST_SHA_V1),
            ("v2", args.v2, FROZEN_MANIFEST_SHA_V2)):
        log("== %s public-protocol PC TX simulated-device test ==\n  frozen_dir=%s"
            % (label, frozen_dir))
        try:
            manifest = pc.PublicProtocolManifest(frozen_dir)
        except Exception as e:
            check("%s manifest load" % label, False, str(e))
            continue

        check("%s manifest SHA == frozen constant" % label,
              manifest.sha256() == frozen_sha,
              "%s (want %s)" % (manifest.sha256()[:16], frozen_sha[:16]))
        check("%s manifest source_id/version" % label,
              manifest.source_id in ("fix1-public-protocol-24waveforms",
                                     "fix1v2-waveform-corrected-24waveforms"),
              "%s/%s" % (manifest.source_id, manifest.conversion_version))

        # Every burst file's SHA matches its manifest row (byte-level identity).
        sha_ok = True
        for src, row in sorted(manifest.rows.items()):
            with open(os.path.join(frozen_dir, row["file_name"]), "rb") as f:
                b = f.read()
            if len(b) != pc.TOTAL_BURST_BYTES or \
                    hashlib.sha256(b).hexdigest() != row["burst_sha256"]:
                sha_ok = False
                check("%s burst %s SHA/size" % (label, row["file_name"]), False,
                      "len=%d" % len(b))
                break
        check("%s all 24 burst files byte-verified" % label, sha_ok, "")

        # Full simulated-device control flow (24 frames, mock TX).
        for name, ok, detail in pc.run_mock_control_flow(frozen_dir, pc.INPUT_KIND, n_frames=24):
            check("%s: %s" % (label, name), ok, detail)

        # Fail-closed: wrong manifest_sha256 in HELLO must be refused.
        eng = pc.PublicProtocolTxEngine(
            pc.MockTxDevice(), frozen_dir, pc.INPUT_KIND,
            pc.DEFAULT_TX_BW_HZ, pc.DEFAULT_TX_ATTEN_DB)
        rejected = False
        try:
            eng.on_hello(_FakeSession("radioml-independent-rx", "n", "0" * 64),
                         {"input_kind": pc.INPUT_KIND,
                          "sample_rate": pc.DEFAULT_SAMPLE_RATE_HZ,
                          "center_hz": pc.DEFAULT_CENTER_HZ,
                          "target_rms": 2048.0})
        except pc.TxEngineError:
            rejected = True
        check("%s wrong manifest_sha256 rejected" % label, rejected, "")

        # Fail-closed: wrong payload_sha_pre in PREPARE must be refused.
        eng2 = pc.PublicProtocolTxEngine(
            pc.MockTxDevice(), frozen_dir, pc.INPUT_KIND,
            pc.DEFAULT_TX_BW_HZ, pc.DEFAULT_TX_ATTEN_DB)
        eng2._manifest = manifest
        eng2._dev.open()
        eng2._dev.configure(pc.DEFAULT_CENTER_HZ, pc.DEFAULT_SAMPLE_RATE_HZ,
                            pc.DEFAULT_TX_BW_HZ, pc.DEFAULT_TX_ATTEN_DB)
        row1 = manifest.lookup(1)
        rejected2 = False
        try:
            eng2.on_prepare(None, {"source_index": 1, "file_name": row1["file_name"],
                                   "payload_sha_pre": "f" * 64})
        except pc.TxEngineError:
            rejected2 = True
        check("%s wrong payload_sha_pre rejected" % label, rejected2, "")

    log("\npass=%d fail=%d" % (g_pass, g_fail))
    return 0 if g_fail == 0 else 1


# --- R1 counterexamples: real TX restore writes .value + readback, mock restore
# actually restores, and a failed restore propagates tx_restore_ok=false. ----------

class _FakeAttr:
    """Mimics pylibiio's ChannelAttr/DeviceAttr: a mutable string .value."""
    def __init__(self, value):
        self.value = value


class _FakeChannel:
    """Mimics pylibiio's Channel: .attrs is a dict name -> ChannelAttr."""
    def __init__(self, **attrs):
        self.attrs = {name: _FakeAttr(str(v)) for name, v in attrs.items()}


class _StickyChannel:
    """A channel whose .value writes are silently ignored (simulates a failed write)."""
    class _Attr:
        def __init__(self, value):
            self._v = value
        @property
        def value(self):
            return self._v
        @value.setter
        def value(self, v):
            pass

    def __init__(self, **attrs):
        self.attrs = {name: self._Attr(str(v)) for name, v in attrs.items()}


class _FakePhy:
    def __init__(self, loopback):
        self.debug_attrs = {"loopback": _FakeAttr(str(loopback))}


def _run_restore_counterexamples(check):
    saved = {"tx_lo": 2450000000, "tx_sample_rate": 2560000, "tx_bw": 18000000,
             "tx_atten": -40.0, "loopback": 0}

    # (a) restore writes the EXISTING ChannelAttr's .value (not attrs.__setitem__).
    dev = pc.PlutoTxDevice.__new__(pc.PlutoTxDevice)
    dev._ctx = object()
    dev._phy = _FakePhy(saved["loopback"])
    dev._tx_ctrl = _FakeChannel(sampling_frequency=saved["tx_sample_rate"],
                                hardwaregain="%.2f" % saved["tx_atten"],
                                rf_bandwidth=saved["tx_bw"])
    dev._tx_lo = _FakeChannel(frequency=saved["tx_lo"])
    dev._saved = dict(saved)
    ok = dev.restore()
    check("R1 PlutoTxDevice.restore() returns True", ok, "")
    attr = dev._tx_lo.attrs["frequency"]
    check("R1 restore keeps ChannelAttr (not a str)",
          isinstance(attr, _FakeAttr), "type=%s" % type(attr).__name__)
    check("R1 restore wrote .value == saved tx_lo",
          attr.value == "2450000000", "value=%r" % (attr.value,))
    check("R1 restore readback tx_lo == saved",
          dev._rd_ll(dev._tx_lo, "frequency") == saved["tx_lo"], "")
    check("R1 restore readback sample_rate == saved",
          dev._rd_ll(dev._tx_ctrl, "sampling_frequency") == saved["tx_sample_rate"], "")
    check("R1 restore readback tx_bw == saved",
          dev._rd_ll(dev._tx_ctrl, "rf_bandwidth") == saved["tx_bw"], "")
    check("R1 restore readback tx_atten == saved",
          abs(dev._rd_d(dev._tx_ctrl, "hardwaregain") - saved["tx_atten"]) <= 0.5, "")
    check("R1 restore readback loopback == saved",
          dev._rd_dbg_ll(dev._phy, "loopback") == saved["loopback"], "")

    # (b) a silently-ignored write must be caught by readback -> restore False.
    bad = pc.PlutoTxDevice.__new__(pc.PlutoTxDevice)
    bad._ctx = object()
    bad._phy = _FakePhy(saved["loopback"])
    bad._tx_ctrl = _FakeChannel(sampling_frequency=saved["tx_sample_rate"],
                                hardwaregain="%.2f" % saved["tx_atten"],
                                rf_bandwidth=saved["tx_bw"])
    bad._tx_lo = _StickyChannel(frequency="2400000000")  # write ignored -> stays wrong
    bad._saved = dict(saved)  # tx_lo=2450000000
    check("R1 silent non-write caught (restore False)", bad.restore() is False, "")

    # (c) MockTxDevice.restore() must actually restore the saved state.
    mdev = pc.MockTxDevice()
    mdev.open()
    mdev.configure(2400000000, 2560000, 18000000, -40.0)
    mdev.start_cyclic(b"\x00" * (pc.TOTAL_BURST_COMPLEX * 4), pc.TOTAL_BURST_COMPLEX)
    check("R1 MockTxDevice running before restore", mdev.running(), "")
    check("R1 MockTxDevice.restore() returns True", mdev.restore(), "")
    check("R1 MockTxDevice stopped after restore", not mdev.running(), "")
    check("R1 MockTxDevice restored saved atten",
          abs(mdev.readback()["tx_atten"] - pc.SAFE_TX_ATTEN_DB) <= 0.01,
          "atten=%.3f" % mdev.readback()["tx_atten"])

    # (d) a failed restore must propagate tx_restore_ok=false through on_captured.
    class _FailingRestore(pc.MockTxDevice):
        def restore(self):
            return False
    fdev = _FailingRestore()
    fdev.open()
    eng = pc.PublicProtocolTxEngine(fdev, os.path.dirname(__file__), pc.INPUT_KIND,
                                    pc.DEFAULT_TX_BW_HZ, pc.DEFAULT_TX_ATTEN_DB)
    res = eng.on_captured(None, {"source_index": 1})
    check("R1 failed restore -> tx_restore_ok=false",
          res.get("tx_restore_ok") is False, "%r" % (res,))


class _FakeSession:
    def __init__(self, session_id, run_nonce, manifest_sha256):
        self.session_id = session_id
        self.run_nonce = run_nonce
        self.manifest_sha256 = manifest_sha256


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
