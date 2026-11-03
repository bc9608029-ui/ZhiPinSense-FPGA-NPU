#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pc_tx_sdr_fix10.py -- fix10prep2 PC-side TX SDR service (radioconda + pylibiio 0.26).

Real dual-SDR topology: the Windows PC owns the TX ADALM-Pluto and periodically
emits the frozen CI16 training-frame burst over 50-ohm coax; the board owns the RX
Pluto and captures it.  The two ends exchange ONLY control messages + sample
identity + SHA over a TCP control channel (fix10_tx_protocol.py) -- never real-time
IQ over the network, never an RX device on this side.

This process is the SERVER peer of the board's control-channel CLIENT.  It:
  * opens + configures the TX SDR (control plane) but does NOT transmit at startup;
  * builds the EXACT training-frame burst the board expects, via the shared h5 C++
    header compiled in WSL (build_burst_cli.sh) -- Python never re-implements the
    frame math (rounding / LCG / Zadoff-Chu drift are a red line);
  * creates the cyclic TX buffer ONLY on a legal START (authorization), never at
    PREPARE/PREPARED (task book section 7 hard rule);
  * sends READY only after TX is running AND every config read-back passed;
  * stops TX on CAPTURED, ABORT, disconnect, protocol error, or exception, and runs
    an INDEPENDENT watchdog (<= 2 s) so a dead connection can never leave the TX
    transmitting without the board having sent STOP.

No RX API is present anywhere here (no cf-ad9361-lpc device, no rx buffer, no RX
gain/LO).  The RX SDR belongs to the board alone.

Run (isolated mode, so no same-name module can be picked up from CWD/another env):
    D:\\radioconda\\python.exe -I host_tools\\pc_tx_sdr_fix10.py --listen 0.0.0.0:39010 ^
        --tx-uri "<PC_TX_URI>" --frozen-dir "<FROZEN_DIR>" ^
        --input-kind radioml-d2-2p56m --center 2400000000 --sample-rate 2560000 ^
        --tx-bw 18000000 --tx-atten -40 --rf-path direct-cable --rf-tx-target-rms 2048

Self-test (verifies the radioconda libiio 0.26 DLL, the package protocol module, and
the WSL burst-tool compile; no device / no RF):
    D:\\radioconda\\python.exe -I host_tools\\pc_tx_sdr_fix10.py --self-test
"""

import argparse
import array
import ctypes.util as _ctu
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

# ---------------------------------------------------------------------------
# libiio DLL resolution + monkeypatch (must precede `import iio`).
#
# radioconda pylibiio builds its CDLL with use_last_error=True, which defeats
# os.add_dll_directory / absolute-path preloads on Windows.  The only reliable fix
# is to patch ctypes.util.find_library for the DLL name pylibiio looks up
# (iio.py:222 `_iiolib = "libiio.dll"`).  The patch must be in place BEFORE the
# first `import iio`, because iio.py binds find_library at its own import time.
# ---------------------------------------------------------------------------
def _radioconda_libiio_dll():
    env = os.environ.get("RADIOCONDA_LIBIIO_DLL")
    if env:
        return env
    exe_dir = os.path.dirname(sys.executable) if sys.executable else ""
    if exe_dir:
        candidate = os.path.join(exe_dir, "Library", "bin", "libiio.dll")
        if os.path.exists(candidate):
            return candidate
    return r"D:\radioconda\Library\bin\libiio.dll"


_RADIOCONDA_LIBIIO = _radioconda_libiio_dll()
_ORIG_FIND_LIBRARY = _ctu.find_library


def _patched_find_library(name):
    if name in ("libiio", "libiio.dll", "iio"):
        return _RADIOCONDA_LIBIIO
    return _ORIG_FIND_LIBRARY(name)


_ctu.find_library = _patched_find_library

import iio  # noqa: E402  (now loads radioconda 0.26)

# ---------------------------------------------------------------------------
# Protocol module -- loaded by absolute path so `python -I` isolated mode never
# silently binds a same-name module from CWD or another environment.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_protocol_module():
    """Return the fix10_tx_protocol module bound to THIS package's host_tools."""
    spec = importlib.util.spec_from_file_location(
        "fix10_tx_protocol", os.path.join(_HERE, "fix10_tx_protocol.py"))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot locate fix10_tx_protocol.py next to pc_tx_sdr_fix10.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


proto = _load_protocol_module()

# ---------------------------------------------------------------------------
# Frozen constants (mirror the C++ headers; the authoritative frame numbers come
# from build_burst_cli --self-check / the tool manifest, not these).
# ---------------------------------------------------------------------------
SAFE_TX_ATTEN_DB = -89.75     # max-safe TX attenuation floor (pluto_tx.hpp)
DEFAULT_PORT = proto.DEFAULT_PORT
WATCHDOG_TIMEOUT_MS = proto.WATCHDOG_TIMEOUT_MS
DEFAULT_SAMPLE_RATE_HZ = 2560000
DEFAULT_CENTER_HZ = 2400000000
DEFAULT_TX_BW_HZ = 18000000
DEFAULT_TX_ATTEN_DB = -40.0
DEFAULT_TARGET_RMS = 2048.0


def manifest_name_for_kind(input_kind):
    """Select the frozen manifest filename by --input-kind, fail-closed (any
    unknown kind raises ManifestError -- never a silent fallback).  This is the
    PC's twin of the board's clean2b::manifest_name_for_kind."""
    if input_kind == "radioml-d2-2p56m":
        return "route_d2_rf_manifest.tsv"
    if input_kind == "radioml-compatible-clean-d2-2p56m":
        return "clean2b_smoke_manifest.tsv"
    raise ManifestError("unknown --input-kind: %s "
                        "(use radioml-d2-2p56m|radioml-compatible-clean-d2-2p56m)"
                        % input_kind)

# Windows console streams default to the ANSI code page (GBK on a Chinese Windows),
# which cannot encode U+FFFD and can mangle non-ASCII paths.  Reconfigure to UTF-8 so
# log()/log_err() never crash mid-session.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def log(msg):
    """One stdout line, flushed, with the FIX10PREP2_PC prefix (mirrors board log
    tokens so a dual-sided log can be diffed)."""
    sys.stdout.write("FIX10PREP2_PC " + msg + "\n")
    sys.stdout.flush()


def log_err(msg):
    sys.stderr.write("FIX10PREP2_PC_ERROR " + msg + "\n")
    sys.stderr.flush()


class TxEngineError(Exception):
    """A TX-device / burst-build / identity failure (not a protocol violation)."""


class ManifestError(Exception):
    """A malformed frozen manifest."""


def windows_to_wsl(p):
    """Translate a Windows path to its WSL mount path: F:\\x\\y -> /mnt/f/x/y."""
    p = os.path.abspath(p)
    drive, rest = os.path.splitdrive(p)
    if drive:
        letter = drive[0].lower()
        return "/mnt/" + letter + rest.replace("\\", "/")
    return p.replace("\\", "/")


# ---------------------------------------------------------------------------
# Frozen manifest index (route_d2_rf_manifest.tsv, 24 columns -- the same column
# map load_d2_sidecar() parses).
# ---------------------------------------------------------------------------
class ManifestIndex:
    def __init__(self, frozen_dir, input_kind):
        self.path = os.path.join(frozen_dir, manifest_name_for_kind(input_kind))
        self.raw = b""
        self.rows = {}   # source_index -> row dict
        self._load()

    def _load(self):
        with open(self.path, "rb") as f:
            self.raw = f.read()
        text = self.raw.decode("utf-8")
        first = True
        for raw_line in text.split("\n"):
            line = raw_line.rstrip("\r")
            if line == "":
                continue
            if line[0] == "#":
                first = False
                continue
            if first:
                first = False
                continue   # header row (24 columns)
            f = line.split("\t")
            if len(f) < 24:
                raise ManifestError("malformed route_d2_rf_manifest.tsv row "
                                    "(expected 24 columns): " + line)
            source_index = int(f[1])
            row = {
                "source_index": source_index,
                "modulation": f[4],
                "split_role": f[6],
                "complex_count": int(f[12]),
                "sample_rate": int(f[13]),
                "original_sha256": f[19],
                "quantized_sha256": f[20],
                "file_name": f[22],
            }
            if source_index in self.rows:
                raise ManifestError("duplicate source_index %d in manifest" % source_index)
            self.rows[source_index] = row
        if not self.rows:
            raise ManifestError("zero rows in route_d2_rf_manifest.tsv")

    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()

    def lookup(self, source_index):
        if source_index not in self.rows:
            raise ManifestError("source_index %d not in manifest" % source_index)
        return self.rows[source_index]


# ---------------------------------------------------------------------------
# BurstBuilder -- invokes the WSL g++ tool (build_burst_cli.sh) which #include's
# the SAME h5 iq_rf_training_frame.hpp / iq_digital_loopback.hpp the board uses,
# so payload_sha_pre / payload_sha_post / burst_sha / tx_scale are byte-identical.
# The tool compiles ONCE and caches the binary keyed by the full preprocessor
# dependency closure (tool + h5 headers), so no per-START recompile happens.
# ---------------------------------------------------------------------------
class BurstBuilder:
    def __init__(self):
        self.tool_sh = os.path.join(_HERE, "build_burst_cli.sh")

    def build(self, ci16_path, complex_count, expect_sha, target_rms, work_dir):
        """Build the burst, return (burst_bytes, provenance dict).  Fail-closed on a
        tool error, a SHA/length mismatch, or a clip."""
        wsl_sh = windows_to_wsl(self.tool_sh)
        wsl_ci16 = windows_to_wsl(ci16_path)
        wsl_burst = windows_to_wsl(os.path.join(work_dir, "burst.bin"))
        wsl_json = windows_to_wsl(os.path.join(work_dir, "manifest.json"))
        cmd = ["wsl.exe", "bash", wsl_sh,
               "--ci16", wsl_ci16,
               "--complex-count", str(int(complex_count)),
               "--expect-sha", expect_sha,
               "--target-rms", repr(float(target_rms)),
               "--out-burst", wsl_burst,
               "--out-json", wsl_json]
        # wsl.exe may emit a non-GBK console warning on stderr; decode UTF-8 with
        # ignore so a stray byte never crashes the reader thread (we only parse the
        # ASCII tool output).
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="ignore")
        if proc.returncode != 0:
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()
            raise TxEngineError(
                "burst build failed (exit %d): %s%s"
                % (proc.returncode, out, (" | " + err) if err else ""))

        burst_path = os.path.join(work_dir, "burst.bin")
        json_path = os.path.join(work_dir, "manifest.json")
        with open(json_path, "r", encoding="utf-8") as f:
            prov = json.load(f)
        with open(burst_path, "rb") as f:
            burst_bytes = f.read()

        # Re-verify every provenance claim on the PC side (belt-and-suspenders).
        for key in ("payload_sha_pre", "payload_sha_post", "burst_sha"):
            if not proto.valid_sha64(prov.get(key, "")):
                raise TxEngineError("burst manifest: bad %s" % key)
        if prov["payload_sha_pre"] != expect_sha:
            raise TxEngineError("burst manifest: payload_sha_pre mismatch")
        if prov.get("clip_pre") or prov.get("clip_post"):
            raise TxEngineError("burst build: waveform clips (pre=%s post=%s)"
                                % (prov.get("clip_pre"), prov.get("clip_post")))
        burst_complex = int(prov["burst_complex"])
        burst_bytes_n = int(prov["burst_bytes"])
        if burst_bytes_n != burst_complex * 4 or len(burst_bytes) != burst_bytes_n:
            raise TxEngineError("burst build: burst byte/complex count mismatch")
        if hashlib.sha256(burst_bytes).hexdigest() != prov["burst_sha"]:
            raise TxEngineError("burst build: burst_sha mismatch on disk bytes")
        return burst_bytes, prov


# ---------------------------------------------------------------------------
# TxEngine -- the injected TX-SDR actions.  Implements the PcTxServerEngine
# interface fix10_tx_protocol.py expects:
#   on_hello -> {tx_serial, tx_uri, tx_atten_db, configuration_verified}
#   on_prepare -> {payload_sha_post, burst_sha, tx_scale}
#   on_start -> {payload_sha_pre, payload_sha_post, burst_sha, tx_scale,
#                sample_rate_readback, tx_lo_readback, tx_bw_readback,
#                tx_atten_readback, tx_running}
#   on_captured -> {tx_restore_ok}
#   on_abort / on_activity / emergency_stop / tx_running / inactive_ms
# ---------------------------------------------------------------------------
class TxEngine:
    def __init__(self, tx_uri, frozen_dir, input_kind, tx_bw_hz, tx_atten_db):
        self.tx_uri = tx_uri
        self.frozen_dir = frozen_dir
        self.input_kind = input_kind
        self.tx_bw_hz = int(tx_bw_hz)
        self.tx_atten_db = float(tx_atten_db)
        self._lock = threading.Lock()
        self._last_activity = time.monotonic()
        self._ctx = None
        self._phy = None
        self._tx_dma = None
        self._tx_ctrl = None      # ad9361-phy voltage0 output=true
        self._tx_lo = None        # ad9361-phy altvoltage1 output=true
        self._tx_i = None         # cf-ad9361-dds-core-lpc voltage0 output=true
        self._tx_q = None         # cf-ad9361-dds-core-lpc voltage1 output=true
        self._txbuf = None
        self._serial = ""
        self._saved = None        # original control-plane snapshot (for restore)
        self._manifest = None
        self._current = None      # prepared burst provenance + bytes
        self._work_dir = None
        self._target_rms = DEFAULT_TARGET_RMS  # HELLO's target_rms (authoritative)
        self._center_hz = 0                     # HELLO's center_hz (re-configured per START)
        self._sample_rate = 0                   # HELLO's sample_rate (re-configured per START)
        self._builder = BurstBuilder()

    # -- watchdog / activity ------------------------------------------------
    def on_activity(self):
        with self._lock:
            self._last_activity = time.monotonic()

    def inactive_ms(self):
        with self._lock:
            return (time.monotonic() - self._last_activity) * 1000.0

    def tx_running(self):
        with self._lock:
            return self._txbuf is not None

    # -- control-channel callbacks ------------------------------------------
    def on_hello(self, session, hello):
        # Identity fail-closed: the PC's frozen dir must byte-match the board's.
        self._manifest = ManifestIndex(self.frozen_dir, self.input_kind)
        pc_manifest_sha = self._manifest.sha256()
        if pc_manifest_sha != session.manifest_sha256:
            log_err("manifest_sha256 mismatch (pc=%s board=%s)"
                    % (pc_manifest_sha, session.manifest_sha256))
            raise TxEngineError("manifest_sha256 mismatch (frozen dir differs from board)")
        if hello["input_kind"] != self.input_kind:
            log_err("input_kind mismatch (cli=%s hello=%s)"
                    % (self.input_kind, hello["input_kind"]))
            raise TxEngineError("input_kind mismatch")

        # HELLO's target_rms is authoritative for the burst scale (never the CLI
        # fallback): it is the exact double the board recomputes tx_scale from.
        self._target_rms = float(hello["target_rms"])
        self._center_hz = int(hello["center_hz"])
        self._sample_rate = int(hello["sample_rate"])

        try:
            self._open_device()
            self._configure_tx(hello["center_hz"], hello["sample_rate"],
                               self.tx_bw_hz, self.tx_atten_db)
            ok, report = self._verify_config(hello["center_hz"], hello["sample_rate"])
        except TxEngineError as e:
            log_err("TX configure failed: %s" % e)
            raise

        if ok:
            log("HELLO_ACK configuration_verified=true tx_serial=%s tx_uri=%s "
                "tx_atten_db=%.3f center_hz=%s sample_rate=%s target_rms=%.6g"
                % (self._serial, self.tx_uri, self._tx_atten_readback(),
                   hello["center_hz"], hello["sample_rate"], hello["target_rms"]))
        else:
            log_err("TX config read-back mismatch: %s" % report)

        return {
            "tx_serial": self._serial,
            "tx_uri": self.tx_uri,
            "tx_atten_db": self._tx_atten_readback(),
            "configuration_verified": ok,
        }

    def on_prepare(self, session, sample):
        # Fail-closed identity: the board's (source_index, file_name, payload_sha_pre)
        # must match the PC's manifest, then build the burst (NO TX).
        row = self._manifest.lookup(sample["source_index"])
        if row["file_name"] != sample["file_name"]:
            raise TxEngineError("file_name mismatch: board=%s manifest=%s"
                                % (sample["file_name"], row["file_name"]))
        if row["quantized_sha256"] != sample["payload_sha_pre"]:
            raise TxEngineError("payload_sha_pre mismatch: board=%s manifest=%s"
                                % (sample["payload_sha_pre"], row["quantized_sha256"]))
        ci16_path = os.path.join(self.frozen_dir, row["file_name"])
        if self._work_dir is None:
            self._work_dir = tempfile.mkdtemp(prefix="fix10prep2_burst_")
        burst_bytes, prov = self._builder.build(
            ci16_path, row["complex_count"], sample["payload_sha_pre"],
            self._target_rms, self._work_dir)

        self._current = {
            "source_index": sample["source_index"],
            "file_name": sample["file_name"],
            "payload_sha_pre": prov["payload_sha_pre"],
            "payload_sha_post": prov["payload_sha_post"],
            "burst_sha": prov["burst_sha"],
            "tx_scale": float(prov["tx_scale"]),
            "burst_bytes": burst_bytes,
            "burst_complex": int(prov["burst_complex"]),
        }
        log("PREPARED source_index=%d file_name=%s payload_sha_post=%s burst_sha=%s "
            "tx_scale=%.17g (built, NOT transmitted)"
            % (sample["source_index"], sample["file_name"],
               prov["payload_sha_post"], prov["burst_sha"], prov["tx_scale"]))
        return {
            "payload_sha_post": prov["payload_sha_post"],
            "burst_sha": prov["burst_sha"],
            "tx_scale": float(prov["tx_scale"]),
        }

    def on_start(self, session, sample):
        # Only here may TX emit.  A prior CAPTURED restored the TX to its original
        # snapshot, so re-apply the burst config, then verify the read-back BEFORE
        # reporting READY (issue #6: a wrong read-back must never send READY).
        if self._current is None:
            raise TxEngineError("START without a prepared burst")
        if (self._current["source_index"] != sample["source_index"] or
                self._current["file_name"] != sample["file_name"]):
            raise TxEngineError("START sample identity mismatch vs prepared burst")

        self._configure_tx(self._center_hz, self._sample_rate,
                           self.tx_bw_hz, self.tx_atten_db)
        self._start_tx(self._current["burst_bytes"], self._current["burst_complex"])
        rb = self._readback_tx()
        ok, report = self._verify_config(self._center_hz, self._sample_rate)
        if not ok:
            with self._lock:
                self._tx_stop_locked()
            raise TxEngineError("TX config read-back mismatch at START: " + report)
        log("READY tx_running=true source_index=%d sample_rate_readback=%d "
            "tx_lo_readback=%d tx_bw_readback=%d tx_atten_readback=%.3f"
            % (sample["source_index"], rb["sample_rate"], rb["tx_lo"],
               rb["tx_bw"], rb["tx_atten"]))
        return {
            "payload_sha_pre": self._current["payload_sha_pre"],
            "payload_sha_post": self._current["payload_sha_post"],
            "burst_sha": self._current["burst_sha"],
            "tx_scale": self._current["tx_scale"],
            "sample_rate_readback": rb["sample_rate"],
            "tx_lo_readback": rb["tx_lo"],
            "tx_bw_readback": rb["tx_bw"],
            "tx_atten_readback": rb["tx_atten"],
            "tx_running": True,
        }

    def on_captured(self, session, sample):
        with self._lock:
            stop_ok = self._tx_stop_locked()
            restore_ok = self._restore_params_locked()
        ok = stop_ok and restore_ok
        log("STOPPED source_index=%d tx_restore_ok=%s stop_ok=%s restore_ok=%s"
            % (sample["source_index"], "true" if ok else "false",
               "true" if stop_ok else "false", "true" if restore_ok else "false"))
        self._current = None
        return {"tx_restore_ok": ok}

    def on_abort(self, session, reason):
        log("ABORT received reason=%s" % reason)

    # -- safety: idempotent TX stop (called on every exit path) -------------
    def emergency_stop(self):
        with self._lock:
            self._tx_stop_locked()
            self._restore_params_locked()
        self._cleanup_work_dir()

    def _cleanup_work_dir(self):
        wd = self._work_dir
        self._work_dir = None
        if wd and os.path.isdir(wd):
            try:
                shutil.rmtree(wd, ignore_errors=True)
            except OSError:
                pass

    # -- libiio TX device (RX-free: no cf-ad9361-lpc, no rx channel, no rx buffer)
    def _open_device(self):
        try:
            self._ctx = iio.Context(self.tx_uri)
        except OSError as e:
            raise TxEngineError("cannot open TX SDR '%s': %s" % (self.tx_uri, e))
        self._phy = self._ctx.find_device("ad9361-phy")
        self._tx_dma = self._ctx.find_device("cf-ad9361-dds-core-lpc")
        if self._phy is None or self._tx_dma is None:
            raise TxEngineError("unexpected device (missing ad9361-phy / "
                                "cf-ad9361-dds-core-lpc)")
        self._tx_ctrl = self._phy.find_channel("voltage0", True)
        self._tx_lo = self._phy.find_channel("altvoltage1", True)
        self._tx_i = self._tx_dma.find_channel("voltage0", True)
        self._tx_q = self._tx_dma.find_channel("voltage1", True)
        if None in (self._tx_ctrl, self._tx_lo, self._tx_i, self._tx_q):
            raise TxEngineError("unexpected device (missing TX channel)")
        self._tx_i.enabled = True
        self._tx_q.enabled = True
        self._serial = self._ctx.attrs.get("hw_serial", "")
        self._saved = {
            "tx_lo": self._rd_attr_ll(self._tx_lo, "frequency"),
            "tx_sample_rate": self._rd_attr_ll(self._tx_ctrl, "sampling_frequency"),
            "tx_bw": self._rd_attr_ll(self._tx_ctrl, "rf_bandwidth"),
            "tx_atten": self._rd_attr_d(self._tx_ctrl, "hardwaregain"),
            "loopback": self._rd_dbg_ll(self._phy, "loopback"),
        }

    def _configure_tx(self, center_hz, sample_rate_hz, tx_bw_hz, tx_atten_db):
        # Fixed order (mirrors pluto_tx.hpp prepare()): safe floor atten first,
        # then LO / sample rate / bw / loopback, then ramp to working atten.
        self._wr_attr(self._tx_ctrl, "hardwaregain", "%.2f" % SAFE_TX_ATTEN_DB)
        self._wr_attr(self._tx_lo, "frequency", str(int(center_hz)))
        self._wr_attr(self._tx_ctrl, "sampling_frequency", str(int(sample_rate_hz)))
        self._wr_attr(self._tx_ctrl, "rf_bandwidth", str(int(tx_bw_hz)))
        self._wr_dbg(self._phy, "loopback", "0")     # external RF (50-ohm coax)
        self._wr_attr(self._tx_ctrl, "hardwaregain", "%.2f" % float(tx_atten_db))

    def _verify_config(self, center_hz, sample_rate_hz):
        rb = self._readback_tx()
        ok = True
        report = []
        if rb["loopback"] != 0:
            ok = False
            report.append("loopback=%d (want 0)" % rb["loopback"])
        if abs(rb["sample_rate"] - int(sample_rate_hz)) > 5:
            ok = False
            report.append("sample_rate=%d (want %d)" % (rb["sample_rate"], sample_rate_hz))
        if abs(rb["tx_lo"] - int(center_hz)) > 5:
            ok = False
            report.append("tx_lo=%d (want %d)" % (rb["tx_lo"], center_hz))
        if abs(rb["tx_atten"] - float(self.tx_atten_db)) > 0.5:
            ok = False
            report.append("tx_atten=%.3f (want %.3f)" % (rb["tx_atten"], self.tx_atten_db))
        if abs(rb["tx_bw"] - int(self.tx_bw_hz)) > max(1000, int(self.tx_bw_hz) // 10):
            ok = False
            report.append("tx_bw=%d (want %d)" % (rb["tx_bw"], self.tx_bw_hz))
        return ok, "; ".join(report)

    def _readback_tx(self):
        return {
            "sample_rate": self._rd_attr_ll(self._tx_ctrl, "sampling_frequency"),
            "tx_lo": self._rd_attr_ll(self._tx_lo, "frequency"),
            "tx_bw": self._rd_attr_ll(self._tx_ctrl, "rf_bandwidth"),
            "tx_atten": self._rd_attr_d(self._tx_ctrl, "hardwaregain"),
            "loopback": self._rd_dbg_ll(self._phy, "loopback"),
        }

    def _tx_atten_readback(self):
        return float(self._tx_ctrl.attrs["hardwaregain"].value)

    def _start_tx(self, burst_bytes, n_complex):
        with self._lock:
            self._tx_stop_locked()
            self._txbuf = iio.Buffer(self._tx_dma, n_complex, cyclic=True)
            arr = array.array("h")
            arr.frombytes(burst_bytes)
            if arr.itemsize != 2 or len(arr) != 2 * n_complex:
                self._txbuf = None
                raise TxEngineError("burst byte/complex mismatch before TX")
            i_bytes = bytearray(arr[0::2].tobytes())
            q_bytes = bytearray(arr[1::2].tobytes())
            # raw=False -> iio_channel_write -> iio_channel_convert_inverse, the same
            # 12-bit convert path the C++ tx_start_cyclic uses (never a raw memcpy).
            self._tx_i.write(self._txbuf, i_bytes, raw=False)
            self._tx_q.write(self._txbuf, q_bytes, raw=False)
            self._txbuf.push(n_complex)

    def _tx_stop_locked(self):
        buf = self._txbuf
        self._txbuf = None
        if buf is None:
            return True   # nothing running -> idempotent success
        try:
            buf.cancel()   # explicit pylibiio Buffer.cancel() (issue #5)
        except Exception:
            return False
        # Drop the last reference so Buffer.__del__ -> iio_buffer_destroy runs now
        # (CPython refcount): this is what actually stops the cyclic TX DMA.
        del buf
        return self._txbuf is None

    def _restore_params_locked(self):
        if self._saved is None or self._ctx is None:
            return False
        saved = self._saved
        ok = True
        try:
            self._tx_lo.attrs["frequency"].value = str(saved["tx_lo"])
        except Exception:
            ok = False
        try:
            self._tx_ctrl.attrs["sampling_frequency"].value = str(saved["tx_sample_rate"])
        except Exception:
            ok = False
        try:
            self._tx_ctrl.attrs["hardwaregain"].value = "%.2f" % saved["tx_atten"]
        except Exception:
            ok = False
        try:
            self._phy.debug_attrs["loopback"].value = str(saved["loopback"])
        except Exception:
            ok = False
        if saved["tx_bw"] != 0:
            try:
                self._tx_ctrl.attrs["rf_bandwidth"].value = str(saved["tx_bw"])
            except Exception:
                ok = False
        # Read-back verification (issue #5): the restored values must actually take,
        # otherwise tx_restore_ok is reported false.
        if ok:
            try:
                rb = self._readback_tx()
                if abs(rb["tx_lo"] - int(saved["tx_lo"])) > 5: ok = False
                if abs(rb["sample_rate"] - int(saved["tx_sample_rate"])) > 5: ok = False
                if abs(rb["tx_atten"] - float(saved["tx_atten"])) > 0.5: ok = False
                if rb["loopback"] != int(saved["loopback"]): ok = False
                if saved["tx_bw"] != 0 and \
                        abs(rb["tx_bw"] - int(saved["tx_bw"])) > max(1000, int(saved["tx_bw"]) // 10):
                    ok = False
            except Exception:
                ok = False
        log("TX state restore=%s" % ("PASS" if ok else "FAIL"))
        return ok

    # -- attribute helpers (string plane, read back parsed) -----------------
    @staticmethod
    def _wr_attr(ch, name, value_str):
        ch.attrs[name].value = value_str

    @staticmethod
    def _wr_dbg(dev, name, value_str):
        dev.debug_attrs[name].value = value_str

    @staticmethod
    def _rd_attr_ll(ch, name):
        return int(round(float(ch.attrs[name].value)))

    @staticmethod
    def _rd_attr_d(ch, name):
        return float(ch.attrs[name].value)

    @staticmethod
    def _rd_dbg_ll(dev, name):
        return int(round(float(dev.debug_attrs[name].value)))


# ---------------------------------------------------------------------------
# Independent watchdog: while the TX is running, if no message has been received
# for > WATCHDOG_TIMEOUT_MS (2 s), stop the TX -- it must never keep transmitting
# without the board having sent STOP.
# ---------------------------------------------------------------------------
class Watchdog(threading.Thread):
    def __init__(self, engine, timeout_ms=WATCHDOG_TIMEOUT_MS):
        super().__init__(daemon=True, name="fix10prep2-watchdog")
        self.engine = engine
        self.timeout_ms = timeout_ms
        self._stop = threading.Event()

    def run(self):
        while not self._stop.wait(0.2):
            if self.engine.tx_running() and self.engine.inactive_ms() > self.timeout_ms:
                log("watchdog: no message for > %d ms while TX running -> stop TX"
                    % self.timeout_ms)
                self.engine.emergency_stop()

    def shutdown(self):
        self._stop.set()


# ---------------------------------------------------------------------------
# Self-test (--self-test): no device, no RF.  Proves (a) radioconda libiio 0.26
# with the iio_get_backends_count symbol, (b) the protocol module is THIS package's
# host_tools copy, (c) no same-name module was shadowed, and (d) the WSL burst tool
# compiles against the h5 headers.  This must be run with radioconda python -I.
# ---------------------------------------------------------------------------
def run_self_test():
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))
        log("SELF-TEST %-34s %s%s"
            % (name, "PASS" if ok else "FAIL", (" -- " + detail) if detail else ""))

    # (a) libiio DLL.
    check("iio.__file__ is radioconda", "radioconda" in getattr(iio, "__file__", ""),
          getattr(iio, "__file__", ""))
    lib_name = getattr(getattr(iio, "_lib", None), "_name", "")
    check("libiio.dll resolved to radioconda", lib_name.lower() == _RADIOCONDA_LIBIIO.lower(),
          lib_name)
    version = getattr(iio, "version", (0, 0, ""))
    check("libiio version is 0.26", version[0] == 0 and version[1] == 26,
          ".".join(str(x) for x in version))
    has_symbol = hasattr(getattr(iio, "_lib", None), "iio_get_backends_count")
    check("iio_get_backends_count symbol", has_symbol, "loaded at import")
    backends = getattr(iio, "backends", None)
    check("libiio backends enumerated", isinstance(backends, list) and len(backends) > 0,
          ",".join(backends) if backends else "none")

    # (b) protocol module provenance.
    check("protocol module from host_tools",
          os.path.basename(os.path.dirname(getattr(proto, "__file__", ""))) == "host_tools",
          getattr(proto, "__file__", ""))
    check("protocol constants frozen",
          proto.PROTOCOL_VERSION == 1 and proto.DEFAULT_PORT == 39010 and
          proto.MAX_MESSAGE_BYTES == (1 << 20) and proto.WATCHDOG_TIMEOUT_MS <= 2000,
          "protocol=%d port=%d max=%d watchdog_ms=%d"
          % (proto.PROTOCOL_VERSION, proto.DEFAULT_PORT,
             proto.MAX_MESSAGE_BYTES, proto.WATCHDOG_TIMEOUT_MS))

    # (c) no same-name shadowing: the exact module file is the package copy.
    expected = os.path.normcase(os.path.join(_HERE, "fix10_tx_protocol.py"))
    actual = os.path.normcase(os.path.abspath(getattr(proto, "__file__", "")))
    check("no same-name module shadowing", actual == expected,
          "expected=%s got=%s" % (expected, actual))

    # (d) WSL burst tool compiles against the h5 headers (compile-once warm-up).
    builder = BurstBuilder()
    wsl_sh = windows_to_wsl(builder.tool_sh)
    try:
        proc = subprocess.run(["wsl.exe", "bash", wsl_sh, "--self-check"],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="ignore", timeout=180)
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        ok = proc.returncode == 0 and "kTotalBurstComplex=" in out
        check("WSL burst tool --self-check", ok,
              out or err or ("exit %d" % proc.returncode))
    except (OSError, subprocess.TimeoutExpired) as e:
        check("WSL burst tool --self-check", False, str(e))

    # (e) serve-mode argument validation (issue #1): the serve path must reject a
    #     missing --tx-uri/--frozen-dir and an over-ceiling --tx-atten, and accept a
    #     valid serve config -- without touching the nonexistent args.tx_atten_db that
    #     used to crash the serve path on startup.
    def _ns(tx_uri="", frozen_dir="", rf_path="direct-cable", tx_atten=-40.0,
            input_kind="radioml-d2-2p56m"):
        return argparse.Namespace(tx_uri=tx_uri, frozen_dir=frozen_dir,
                                  rf_path=rf_path, tx_atten=tx_atten,
                                  input_kind=input_kind)
    check("serve args: valid config accepted",
          _validate_serve_args(_ns(tx_uri="usb:1.2.3", frozen_dir="C:\\frozen")) is None)
    check("serve args: missing --tx-uri rejected",
          _validate_serve_args(_ns(frozen_dir="C:\\frozen")) is not None)
    check("serve args: missing --frozen-dir rejected",
          _validate_serve_args(_ns(tx_uri="usb:1.2.3")) is not None)
    check("serve args: non-direct-cable rf-path rejected",
          _validate_serve_args(_ns(tx_uri="usb:1.2.3", frozen_dir="C:\\frozen",
                                   rf_path="antenna")) is not None)
    check("serve args: >-40 dB tx-atten rejected",
          _validate_serve_args(_ns(tx_uri="usb:1.2.3", frozen_dir="C:\\frozen",
                                   tx_atten=-30.0)) is not None)

    # (f) input_kind: the serve path must reject an unknown kind and accept both
    #     legal kinds, and ManifestIndex must select the right manifest basename
    #     per kind (the PC's twin of clean2b::manifest_name_for_kind; fail-closed).
    check("serve args: unknown input_kind rejected",
          _validate_serve_args(_ns(tx_uri="usb:1.2.3", frozen_dir="C:\\frozen",
                                   input_kind="radioml-bogus")) is not None)
    check("serve args: clean2b input_kind accepted",
          _validate_serve_args(_ns(tx_uri="usb:1.2.3", frozen_dir="C:\\frozen",
                                   input_kind="radioml-compatible-clean-d2-2p56m")) is None)
    check("serve args: d2 input_kind accepted",
          _validate_serve_args(_ns(tx_uri="usb:1.2.3", frozen_dir="C:\\frozen",
                                   input_kind="radioml-d2-2p56m")) is None)
    name_d2 = manifest_name_for_kind("radioml-d2-2p56m")
    name_clean = manifest_name_for_kind("radioml-compatible-clean-d2-2p56m")
    check("manifest_name_for_kind selects per kind",
          name_d2 == "route_d2_rf_manifest.tsv"
          and name_clean == "clean2b_smoke_manifest.tsv",
          "d2=%s clean2b=%s" % (name_d2, name_clean))
    name_bad = ""
    try:
        manifest_name_for_kind("radioml-bogus")
    except ManifestError as e:
        name_bad = str(e)
    check("manifest_name_for_kind fail-closed on unknown", name_bad != "", name_bad)

    # ManifestIndex builds its path from manifest_name_for_kind (verified via a
    # minimal temp manifest so the real path-selection code is exercised).
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for _name, _cols in (("route_d2_rf_manifest.tsv", 24),
                                 ("clean2b_smoke_manifest.tsv", 27)):
                _row = ["x"] * _cols
                _row[1] = "1500"
                _row[4] = "BPSK"
                _row[6] = "holdout"
                _row[12] = "53760"
                _row[13] = "2560000"
                _row[19] = "a" * 64
                _row[20] = "b" * 64
                _row[22] = "d.ci16"
                with open(os.path.join(tmp, _name), "w", encoding="utf-8") as _fh:
                    _fh.write("\t".join("c%d" % i for i in range(_cols)) + "\n")
                    _fh.write("\t".join(_row) + "\n")
            _idx_d2 = ManifestIndex(tmp, "radioml-d2-2p56m")
            _idx_clean = ManifestIndex(tmp, "radioml-compatible-clean-d2-2p56m")
            check("ManifestIndex path per kind",
                  os.path.basename(_idx_d2.path) == "route_d2_rf_manifest.tsv"
                  and os.path.basename(_idx_clean.path) == "clean2b_smoke_manifest.tsv",
                  "%s | %s" % (_idx_d2.path, _idx_clean.path))
    except Exception as e:  # noqa: BLE001
        check("ManifestIndex path per kind", False, str(e))

    all_ok = all(c[1] for c in checks)
    log("SELF-TEST %s (%d/%d checks)" % ("PASS" if all_ok else "FAIL",
                                          sum(1 for c in checks if c[1]), len(checks)))
    return 0 if all_ok else 1


# ---------------------------------------------------------------------------
def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="pc_tx_sdr_fix10.py",
        description="fix10prep2 PC-side TX SDR service (real dual-SDR, TX-only).")
    p.add_argument("--listen", default="0.0.0.0:%d" % DEFAULT_PORT,
                   help="bind host:port (default 0.0.0.0:%d)" % DEFAULT_PORT)
    p.add_argument("--tx-uri", default="",
                   help="libiio URI of the PC's TX SDR (REQUIRED in serve mode)")
    p.add_argument("--frozen-dir", default="",
                   help="frozen D2 artifacts dir (REQUIRED in serve mode)")
    p.add_argument("--input-kind", default="radioml-d2-2p56m")
    p.add_argument("--center", type=int, default=DEFAULT_CENTER_HZ,
                   help="fallback center Hz (HELLO is authoritative)")
    p.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE_HZ,
                   help="fallback sample rate (HELLO is authoritative)")
    p.add_argument("--tx-bw", type=int, default=DEFAULT_TX_BW_HZ)
    p.add_argument("--tx-atten", type=float, default=DEFAULT_TX_ATTEN_DB,
                   help="TX attenuation dB (<= -40 recommended; never above -40)")
    p.add_argument("--rf-path", default="",
                   help="must be 'direct-cable' to authorize external RF TX")
    p.add_argument("--rf-tx-target-rms", type=float, default=DEFAULT_TARGET_RMS,
                   help="fallback target RMS (HELLO is authoritative)")
    p.add_argument("--self-test", action="store_true",
                   help="run the startup self-test and exit (no device, no RF)")
    return p.parse_args(argv)


def _parse_listen(spec):
    if ":" in spec:
        host, _, port = spec.rpartition(":")
        return host or "0.0.0.0", int(port)
    return "0.0.0.0", int(spec)


def _validate_serve_args(args):
    """Return None if the serve-mode args are valid, else an error message.  This is
    the exact validation the serve path runs (and what --self-test exercises), so the
    serve path can never crash on a missing/renamed attribute (issue #1)."""
    if not args.tx_uri:
        return "--tx-uri is required in serve mode"
    if not args.frozen_dir:
        return "--frozen-dir is required in serve mode"
    if args.input_kind not in ("radioml-d2-2p56m",
                               "radioml-compatible-clean-d2-2p56m"):
        return ("--input-kind must be 'radioml-d2-2p56m' or "
                "'radioml-compatible-clean-d2-2p56m'; got '%s'" % args.input_kind)
    if args.rf_path != "direct-cable":
        return ("--rf-path must be 'direct-cable' (50-ohm SMA coax, no antenna, "
                "no amplifier) to authorize real RF TX; got '%s'" % args.rf_path)
    if args.tx_atten > -40.0:
        return "--tx-atten %.3f exceeds the -40 dB safety ceiling; refusing" % args.tx_atten
    return None


def main(argv):
    args = parse_args(argv)

    if args.self_test:
        return run_self_test()

    # Serve mode: hard requirements (the same checks --self-test exercises via
    # _validate_serve_args, so the serve path's own validation is covered).
    err = _validate_serve_args(args)
    if err:
        log_err(err)
        return 1

    host, port = _parse_listen(args.listen)

    engine = TxEngine(args.tx_uri, args.frozen_dir, args.input_kind,
                      tx_bw_hz=args.tx_bw, tx_atten_db=args.tx_atten)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
        server.listen(1)
    except OSError as e:
        log_err("cannot bind %s:%d: %s" % (host, port, e))
        server.close()
        return 1

    log("listening on %s:%d tx_uri=%s frozen_dir=%s input_kind=%s tx_bw=%d "
        "tx_atten=%.2f rf_path=direct-cable"
        % (host, port, args.tx_uri, args.frozen_dir, args.input_kind,
           args.tx_bw, args.tx_atten))

    try:
        conn, addr = server.accept()
    except OSError as e:
        log_err("accept failed: %s" % e)
        server.close()
        return 1
    log("board connected from %s:%d" % (addr[0], addr[1]))

    wd = Watchdog(engine)
    wd.start()
    rc = 0
    try:
        session = proto.PcTxServerSession(engine, conn)
        session.serve()
    except proto.ProtocolError as e:
        log_err("protocol violation: %s" % e)
        rc = 1
    except (TxEngineError, ManifestError) as e:
        log_err("engine failure: %s" % e)
        rc = 1
    except KeyboardInterrupt:
        log("interrupted (Ctrl+C); stopping TX")
        rc = 130
    finally:
        wd.shutdown()
        engine.emergency_stop()
        conn.close()
        server.close()
    log("session ended; TX stopped")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
