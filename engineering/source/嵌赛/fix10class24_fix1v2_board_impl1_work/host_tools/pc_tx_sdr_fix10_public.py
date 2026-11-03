#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pc_tx_sdr_fix10_public.py -- fix10class24 Task D (G4): public-protocol PC TX service.

This is the PC-side SERVER peer of the board's independent-RX CLIENT control channel
(39010).  It owns the TX ADALM-Pluto and transmits the FROZEN public-protocol
training-frame burst .i16 files -- already scaled to the uniform class-independent S
(v1 117.84922023433009 / v2 71.609111379029812) -- so the PC MUST transmit them AS-IS:
tx_scale == 1.0, NO re-scaling, payload_sha_pre == payload_sha_post == burst_sha ==
the manifest's burst_sha256.  This is the exact provenance the board's runner
(radioml_independent_rx_runner.hpp) asserts fail-closed in PREPARED and READY.

The public burst is NOT the D2 per-class payload: it is the full 59904-complex
training-frame burst (ZC preamble + settling-zero + 16QAM training + 53760 payload +
guard + ZC tail) already quantized to int16 and scaled to S.  There is therefore no
BurstBuilder / no WSL g++ / no re-scale step: the PC reads the frozen .i16 bytes,
verifies their SHA against the manifest, and streams them cyclic on a legal START.

Role of the two ends (real dual-SDR): the PC owns the TX SDR and never opens an RX
device; the board owns the RX SDR and never opens a TX device.  This process exchanges
ONLY control messages + sample identity + SHA over TCP -- never real-time IQ.

Safety: PREPARE/PREPARED never create a cyclic TX buffer; only a legal START transmits;
READY is sent only after TX is running AND every config read-back passed; TX stops on
CAPTURED / ABORT / disconnect / error; an independent <=2 s watchdog stops TX if the
board goes silent while TX is running.

The TX device is injectable: `--mock` selects a simulated device (no libiio, no RF) so
the full control flow + provenance is exercised over 127.0.0.1 with zero hardware.
The real libiio path is imported lazily, so `--mock`/`--self-test` run under plain
`python -I` (no radioconda needed).

Run (real device, radioconda pylibiio 0.26):
    D:\\radioconda\\python.exe -I host_tools\\pc_tx_sdr_fix10_public.py --listen 0.0.0.0:39010 ^
        --tx-uri "<PC_TX_URI>" --frozen-dir "<public_protocol_tx_package>" ^
        --rf-path direct-cable --tx-atten -40

Mock (simulated device, no RF, plain python):
    D:\\Anaconda\\python.exe -I host_tools\\pc_tx_sdr_fix10_public.py --mock ^
        --frozen-dir "<public_protocol_tx_package>" --listen 127.0.0.1:39010

Self-test (no device, no RF, runs the full simulated-device control-flow cycle):
    D:\\Anaconda\\python.exe -I host_tools\\pc_tx_sdr_fix10_public.py --self-test
"""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time

# ---------------------------------------------------------------------------
# Protocol module -- loaded by absolute path so `python -I` isolated mode never
# silently binds a same-name module from CWD or another environment.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_protocol_module():
    spec = importlib.util.spec_from_file_location(
        "fix10_tx_protocol", os.path.join(_HERE, "fix10_tx_protocol.py"))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot locate fix10_tx_protocol.py next to pc_tx_sdr_fix10_public.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


proto = _load_protocol_module()

# ---------------------------------------------------------------------------
# Frozen constants (mirror the board headers).
# ---------------------------------------------------------------------------
MANIFEST_NAME = "public_protocol_tx_manifest.tsv"
INPUT_KIND = "radioml-independent-rx-public-protocol-24class"
TOTAL_BURST_COMPLEX = 59904          # iqrftrain::kTotalBurstComplex
TOTAL_BURST_BYTES = TOTAL_BURST_COMPLEX * 4   # 239616 bytes (int16 interleaved)
SAFE_TX_ATTEN_DB = -89.75            # max-safe TX attenuation floor (pluto_tx.hpp)
DEFAULT_PORT = proto.DEFAULT_PORT
WATCHDOG_TIMEOUT_MS = proto.WATCHDOG_TIMEOUT_MS
DEFAULT_SAMPLE_RATE_HZ = 2560000
DEFAULT_CENTER_HZ = 2400000000
DEFAULT_TX_BW_HZ = 18000000
DEFAULT_TX_ATTEN_DB = -40.0

# Windows console streams default to the ANSI code page (GBK on Chinese Windows).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def log(msg):
    sys.stdout.write("FIX1V2_PC " + msg + "\n")
    sys.stdout.flush()


def log_err(msg):
    sys.stderr.write("FIX1V2_PC_ERROR " + msg + "\n")
    sys.stderr.flush()


class TxEngineError(Exception):
    """A TX-device / identity / manifest failure (not a protocol violation)."""


class ManifestError(Exception):
    """A malformed frozen public-protocol manifest."""


# ---------------------------------------------------------------------------
# Public-protocol frozen manifest (10 columns).
# ---------------------------------------------------------------------------
MANIFEST_HEADER = ("source_id\tconversion_version\tsource_index\tclass_index\t"
                   "class_name\tseed\tburst_file\tburst_sha256\tpayload_ci16_sha256\t"
                   "model_input_sha256")


class PublicProtocolManifest:
    """The 10-column public_protocol_tx_manifest.tsv (v1 AND v2 share the layout)."""

    def __init__(self, frozen_dir):
        self.frozen_dir = frozen_dir
        self.path = os.path.join(frozen_dir, MANIFEST_NAME)
        self.raw = b""
        self.rows = {}          # source_index -> row dict
        self.source_id = ""
        self.conversion_version = ""
        self._load()

    def _load(self):
        try:
            with open(self.path, "rb") as f:
                self.raw = f.read()
        except OSError as e:
            raise ManifestError("cannot read manifest %s: %s" % (self.path, e))
        text = self.raw.decode("utf-8")
        lines = text.split("\n")
        if not lines or lines[0].rstrip("\r") != MANIFEST_HEADER:
            raise ManifestError("manifest header mismatch in %s" % self.path)
        seen = set()
        for raw_line in lines[1:]:
            line = raw_line.rstrip("\r")
            if line == "":
                continue
            f = line.split("\t")
            if len(f) != 10:
                raise ManifestError("malformed manifest row (expected 10 columns): " + line)
            source_index = int(f[2])
            if source_index in seen:
                raise ManifestError("duplicate source_index %d in manifest" % source_index)
            seen.add(source_index)
            sid, ver = f[0], f[1]
            if self.source_id == "":
                self.source_id, self.conversion_version = sid, ver
            elif sid != self.source_id or ver != self.conversion_version:
                raise ManifestError(
                    "manifest mixes (source_id, conversion_version): '%s'/'%s' vs '%s'/'%s'"
                    % (self.source_id, self.conversion_version, sid, ver))
            self.rows[source_index] = {
                "source_index": source_index,
                "class_index": int(f[3]),
                "class_name": f[4],
                "file_name": f[6],
                "burst_sha256": f[7],
            }
        if len(self.rows) != 24:
            raise ManifestError("manifest has %d rows (want 24)" % len(self.rows))

    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()

    def lookup(self, source_index):
        if source_index not in self.rows:
            raise ManifestError("source_index %d not in manifest" % source_index)
        return self.rows[source_index]


# ---------------------------------------------------------------------------
# TX device abstraction (injectable).  The real libiio implementation is imported
# lazily so --mock / --self-test never touch radioconda.
# ---------------------------------------------------------------------------
class TxDevice:
    """The TX-SDR actions the engine needs.  Real (PlutoTxDevice) and mock
    (MockTxDevice) share this interface, so the engine is device-agnostic."""

    def open(self): raise NotImplementedError
    def configure(self, center_hz, sample_rate, bw_hz, atten_db): raise NotImplementedError
    def verify(self, center_hz, sample_rate, bw_hz, atten_db): raise NotImplementedError
    def readback(self): raise NotImplementedError
    def atten_readback(self): raise NotImplementedError
    def start_cyclic(self, burst_bytes, n_complex): raise NotImplementedError
    def stop(self): raise NotImplementedError
    def restore(self): raise NotImplementedError
    def serial(self): raise NotImplementedError
    def uri(self): raise NotImplementedError
    def running(self): raise NotImplementedError


class MockTxDevice(TxDevice):
    """Simulated TX SDR: config echoes back, cyclic TX toggles a flag and records the
    exact burst bytes.  No libiio, no RF, no subprocess."""

    def __init__(self, tx_uri="mock:public-protocol"):
        self._uri = tx_uri
        self._serial = "MOCK-TX-0001"
        self._configured = None          # (center, rate, bw, atten)
        self._running = False
        self._burst_bytes = None
        self._n_complex = 0
        self._saved = {"tx_lo": DEFAULT_CENTER_HZ,
                       "tx_sample_rate": DEFAULT_SAMPLE_RATE_HZ,
                       "tx_bw": DEFAULT_TX_BW_HZ,
                       "tx_atten": SAFE_TX_ATTEN_DB,
                       "loopback": 0}

    def open(self):
        pass

    def configure(self, center_hz, sample_rate, bw_hz, atten_db):
        self._configured = (int(center_hz), int(sample_rate), int(bw_hz), float(atten_db))

    def verify(self, center_hz, sample_rate, bw_hz, atten_db):
        if self._configured != (int(center_hz), int(sample_rate), int(bw_hz), float(atten_db)):
            return False, "mock config mismatch"
        return True, ""

    def readback(self):
        c, r, b, a = self._configured
        return {"sample_rate": r, "tx_lo": c, "tx_bw": b, "tx_atten": a, "loopback": 0}

    def atten_readback(self):
        return self._configured[3]

    def start_cyclic(self, burst_bytes, n_complex):
        if len(burst_bytes) != n_complex * 4:
            raise TxEngineError("mock burst byte/complex mismatch (%d != %d*4)"
                                % (len(burst_bytes), n_complex))
        self._burst_bytes = bytes(burst_bytes)
        self._n_complex = n_complex
        self._running = True

    def stop(self):
        self._running = False
        self._burst_bytes = None
        self._n_complex = 0
        return True

    def restore(self):
        # R1: actually restore the pre-run saved state (previously a no-op `return True`).
        self._running = False
        self._burst_bytes = None
        self._n_complex = 0
        self._configured = (self._saved["tx_lo"], self._saved["tx_sample_rate"],
                            self._saved["tx_bw"], self._saved["tx_atten"])
        return True

    def serial(self):
        return self._serial

    def uri(self):
        return self._uri

    def running(self):
        return self._running


class PlutoTxDevice(TxDevice):
    """Real libiio TX SDR (radioconda pylibiio 0.26).  The libiio import happens only
    when this class is constructed, so the mock/self-test path never needs it."""

    def __init__(self, tx_uri):
        self._iio = _load_iio()
        self.tx_uri = tx_uri
        self._ctx = None
        self._phy = None
        self._tx_dma = None
        self._tx_ctrl = None
        self._tx_lo = None
        self._tx_i = None
        self._tx_q = None
        self._txbuf = None
        self._serial = ""
        self._saved = None

    # -- interface ----------------------------------------------------------
    def open(self):
        try:
            self._ctx = self._iio.Context(self.tx_uri)
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
            "tx_lo": self._rd_ll(self._tx_lo, "frequency"),
            "tx_sample_rate": self._rd_ll(self._tx_ctrl, "sampling_frequency"),
            "tx_bw": self._rd_ll(self._tx_ctrl, "rf_bandwidth"),
            "tx_atten": self._rd_d(self._tx_ctrl, "hardwaregain"),
            "loopback": self._rd_dbg_ll(self._phy, "loopback"),
        }

    def configure(self, center_hz, sample_rate, bw_hz, atten_db):
        self._wr(self._tx_ctrl, "hardwaregain", "%.2f" % SAFE_TX_ATTEN_DB)
        self._wr(self._tx_lo, "frequency", str(int(center_hz)))
        self._wr(self._tx_ctrl, "sampling_frequency", str(int(sample_rate)))
        self._wr(self._tx_ctrl, "rf_bandwidth", str(int(bw_hz)))
        self._wr_dbg(self._phy, "loopback", "0")
        self._wr(self._tx_ctrl, "hardwaregain", "%.2f" % float(atten_db))

    def verify(self, center_hz, sample_rate, bw_hz, atten_db):
        rb = self.readback()
        ok = True
        report = []
        if rb["loopback"] != 0:
            ok = False; report.append("loopback=%d" % rb["loopback"])
        if abs(rb["sample_rate"] - int(sample_rate)) > 5:
            ok = False; report.append("sample_rate=%d" % rb["sample_rate"])
        if abs(rb["tx_lo"] - int(center_hz)) > 5:
            ok = False; report.append("tx_lo=%d" % rb["tx_lo"])
        if abs(rb["tx_atten"] - float(atten_db)) > 0.5:
            ok = False; report.append("tx_atten=%.3f" % rb["tx_atten"])
        if abs(rb["tx_bw"] - int(bw_hz)) > max(1000, int(bw_hz) // 10):
            ok = False; report.append("tx_bw=%d" % rb["tx_bw"])
        return ok, "; ".join(report)

    def readback(self):
        return {
            "sample_rate": self._rd_ll(self._tx_ctrl, "sampling_frequency"),
            "tx_lo": self._rd_ll(self._tx_lo, "frequency"),
            "tx_bw": self._rd_ll(self._tx_ctrl, "rf_bandwidth"),
            "tx_atten": self._rd_d(self._tx_ctrl, "hardwaregain"),
            "loopback": self._rd_dbg_ll(self._phy, "loopback"),
        }

    def atten_readback(self):
        return self._parse_attr(self._tx_ctrl.attrs["hardwaregain"].value, "hardwaregain")

    def start_cyclic(self, burst_bytes, n_complex):
        self.stop()
        self._txbuf = self._iio.Buffer(self._tx_dma, n_complex, cyclic=True)
        arr = self._iio_array("h")
        arr.frombytes(burst_bytes)
        if arr.itemsize != 2 or len(arr) != 2 * n_complex:
            self._txbuf = None
            raise TxEngineError("burst byte/complex mismatch before TX")
        i_bytes = bytearray(arr[0::2].tobytes())
        q_bytes = bytearray(arr[1::2].tobytes())
        self._tx_i.write(self._txbuf, i_bytes, raw=False)
        self._tx_q.write(self._txbuf, q_bytes, raw=False)
        self._txbuf.push(n_complex)

    def stop(self):
        buf = self._txbuf
        self._txbuf = None
        if buf is None:
            return True
        try:
            buf.cancel()
        except Exception:
            return False
        del buf
        return self._txbuf is None

    def restore(self):
        if self._saved is None or self._ctx is None:
            return False
        s = self._saved
        ok = True
        # R1: write the EXISTING ChannelAttr/DeviceAttr object's .value -- never replace
        # the dict entry with a str (attrs.__setitem__ breaks a later configure()'s
        # .value read).  Each write goes through _wr/_wr_dbg, which target .value.
        try:
            self._wr(self._tx_lo, "frequency", str(s["tx_lo"]))
        except Exception:
            ok = False
        try:
            self._wr(self._tx_ctrl, "sampling_frequency", str(s["tx_sample_rate"]))
        except Exception:
            ok = False
        try:
            self._wr(self._tx_ctrl, "hardwaregain", "%.2f" % s["tx_atten"])
        except Exception:
            ok = False
        try:
            self._wr_dbg(self._phy, "loopback", str(s["loopback"]))
        except Exception:
            ok = False
        if s["tx_bw"] != 0:
            try:
                self._wr(self._tx_ctrl, "rf_bandwidth", str(s["tx_bw"]))
            except Exception:
                ok = False
        # R1: read-back verification -- every restored attribute must read back to the
        # saved value; a silent non-write is a restore failure, not success.
        try:
            if self._rd_ll(self._tx_lo, "frequency") != s["tx_lo"]:
                ok = False
            if self._rd_ll(self._tx_ctrl, "sampling_frequency") != s["tx_sample_rate"]:
                ok = False
            if abs(self._rd_d(self._tx_ctrl, "hardwaregain") - s["tx_atten"]) > 0.5:
                ok = False
            if s["tx_bw"] != 0 and self._rd_ll(self._tx_ctrl, "rf_bandwidth") != s["tx_bw"]:
                ok = False
            if self._rd_dbg_ll(self._phy, "loopback") != s["loopback"]:
                ok = False
        except Exception:
            ok = False
        return ok

    def serial(self):
        return self._serial

    def uri(self):
        return self.tx_uri

    def running(self):
        return self._txbuf is not None

    # -- attribute helpers --------------------------------------------------
    def _parse_attr(self, raw, attr):
        # bare float / "x dB" / "x Hz" / scientific, else fail.
        s = str(raw).strip()
        for suffix in (" dB", " Hz"):
            if s.endswith(suffix):
                s = s[: -len(suffix)].strip()
        try:
            return float(s)
        except ValueError:
            raise TxEngineError("cannot parse IIO attr %s=%r" % (attr, raw))

    def _wr(self, ch, name, value_str):
        ch.attrs[name].value = value_str

    def _wr_dbg(self, dev, name, value_str):
        dev.debug_attrs[name].value = value_str

    def _rd_ll(self, ch, name):
        return int(round(self._parse_attr(ch.attrs[name].value, name)))

    def _rd_d(self, ch, name):
        return self._parse_attr(ch.attrs[name].value, name)

    def _rd_dbg_ll(self, dev, name):
        return int(round(self._parse_attr(dev.debug_attrs[name].value, name)))

    def _iio_array(self, typecode):
        import array
        return array.array(typecode)


def _load_iio():
    """Lazy-import radioconda pylibiio 0.26 with the DLL monkeypatch.  Returns the iio
    module.  Only called when a real PlutoTxDevice is constructed."""
    import ctypes.util as _ctu

    env = os.environ.get("RADIOCONDA_LIBIIO_DLL")
    dll = env
    if not dll:
        exe_dir = os.path.dirname(sys.executable) if sys.executable else ""
        cand = os.path.join(exe_dir, "Library", "bin", "libiio.dll") if exe_dir else ""
        if exe_dir and os.path.exists(cand):
            dll = cand
        else:
            dll = r"D:\radioconda\Library\bin\libiio.dll"

    orig = _ctu.find_library

    def patched(name):
        if name in ("libiio", "libiio.dll", "iio"):
            return dll
        return orig(name)

    _ctu.find_library = patched
    import iio  # noqa: F401
    return iio


# ---------------------------------------------------------------------------
# PublicProtocolTxEngine -- the injected engine (implements PcTxServerEngine).
#   on_hello  -> {tx_serial, tx_uri, tx_atten_db, configuration_verified}
#   on_prepare -> {payload_sha_post, burst_sha, tx_scale}   (tx_scale == 1.0 always)
#   on_start  -> {payload_sha_pre, payload_sha_post, burst_sha, tx_scale,
#                 sample_rate_readback, tx_lo_readback, tx_bw_readback,
#                 tx_atten_readback, tx_running}
#   on_captured -> {tx_restore_ok}
# ---------------------------------------------------------------------------
class PublicProtocolTxEngine:
    def __init__(self, device, frozen_dir, input_kind, tx_bw_hz, tx_atten_db):
        self._dev = device
        self._frozen_dir = frozen_dir
        self._input_kind = input_kind
        self._tx_bw_hz = int(tx_bw_hz)
        self._tx_atten_db = float(tx_atten_db)
        self._lock = threading.Lock()
        self._last_activity = time.monotonic()
        self._manifest = None
        self._current = None       # prepared burst: dict(bytes, sha, source_index, file_name)
        self._center_hz = DEFAULT_CENTER_HZ
        self._sample_rate = DEFAULT_SAMPLE_RATE_HZ

    # -- watchdog / activity ------------------------------------------------
    def on_activity(self):
        with self._lock:
            self._last_activity = time.monotonic()

    def inactive_ms(self):
        with self._lock:
            return (time.monotonic() - self._last_activity) * 1000.0

    def tx_running(self):
        return self._dev.running()

    # -- control-channel callbacks ------------------------------------------
    def on_hello(self, session, hello):
        # Identity fail-closed: the PC's frozen public-protocol dir must byte-match
        # the board's (manifest_sha256 is the SHA of the manifest FILE bytes).
        self._manifest = PublicProtocolManifest(self._frozen_dir)
        pc_sha = self._manifest.sha256()
        if pc_sha != session.manifest_sha256:
            raise TxEngineError("manifest_sha256 mismatch (pc=%s board=%s)"
                                % (pc_sha, session.manifest_sha256))
        if hello["input_kind"] != self._input_kind:
            raise TxEngineError("input_kind mismatch (cli=%s hello=%s)"
                                % (self._input_kind, hello["input_kind"]))
        self._center_hz = int(hello["center_hz"])
        self._sample_rate = int(hello["sample_rate"])
        # hello["target_rms"] is unused (the public burst is pre-scaled to S), but it
        # is validated positive by the protocol layer.

        self._dev.open()
        self._dev.configure(self._center_hz, self._sample_rate,
                            self._tx_bw_hz, self._tx_atten_db)
        ok, report = self._dev.verify(self._center_hz, self._sample_rate,
                                      self._tx_bw_hz, self._tx_atten_db)
        if not ok:
            log_err("TX config read-back mismatch: %s" % report)
        log("HELLO_ACK configuration_verified=%s tx_serial=%s tx_uri=%s "
            "tx_atten_db=%.3f center_hz=%d sample_rate=%d source_id=%s version=%s"
            % ("true" if ok else "false", self._dev.serial(), self._dev.uri(),
               self._dev.atten_readback(), self._center_hz, self._sample_rate,
               self._manifest.source_id, self._manifest.conversion_version))
        return {
            "tx_serial": self._dev.serial(),
            "tx_uri": self._dev.uri(),
            "tx_atten_db": self._dev.atten_readback(),
            "configuration_verified": ok,
        }

    def on_prepare(self, session, sample):
        if self._manifest is None:
            raise TxEngineError("PREPARE without HELLO")
        row = self._manifest.lookup(sample["source_index"])
        if row["file_name"] != sample["file_name"]:
            raise TxEngineError("IDENTITY_MISMATCH file_name board=%s manifest=%s"
                                % (sample["file_name"], row["file_name"]))
        burst_path = os.path.join(self._frozen_dir, row["file_name"])
        try:
            with open(burst_path, "rb") as f:
                burst_bytes = f.read()
        except OSError as e:
            raise TxEngineError("cannot read burst %s: %s" % (burst_path, e))
        if len(burst_bytes) != TOTAL_BURST_BYTES:
            raise TxEngineError("burst %s size %d != %d"
                                % (row["file_name"], len(burst_bytes), TOTAL_BURST_BYTES))
        burst_sha = hashlib.sha256(burst_bytes).hexdigest()
        if burst_sha != row["burst_sha256"]:
            raise TxEngineError("burst %s SHA mismatch (manifest=%s file=%s)"
                                % (row["file_name"], row["burst_sha256"], burst_sha))
        if burst_sha != sample["payload_sha_pre"]:
            raise TxEngineError("IDENTITY_MISMATCH payload_sha_pre board=%s file=%s"
                                % (sample["payload_sha_pre"], burst_sha))
        # Public burst is pre-scaled to S: the PC transmits it AS-IS.
        self._current = {
            "source_index": sample["source_index"],
            "file_name": sample["file_name"],
            "payload_sha_pre": burst_sha,
            "burst_sha": burst_sha,
            "burst_bytes": burst_bytes,
        }
        log("PREPARED source_index=%d file_name=%s burst_sha=%s tx_scale=1.0 "
            "(as-is, NOT transmitted)"
            % (sample["source_index"], sample["file_name"], burst_sha))
        return {"payload_sha_post": burst_sha, "burst_sha": burst_sha, "tx_scale": 1.0}

    def on_start(self, session, sample):
        if self._current is None:
            raise TxEngineError("START without a prepared burst")
        if (self._current["source_index"] != sample["source_index"] or
                self._current["file_name"] != sample["file_name"]):
            raise TxEngineError("START sample identity mismatch vs prepared burst")
        self._dev.configure(self._center_hz, self._sample_rate,
                            self._tx_bw_hz, self._tx_atten_db)
        self._dev.start_cyclic(self._current["burst_bytes"], TOTAL_BURST_COMPLEX)
        ok, report = self._dev.verify(self._center_hz, self._sample_rate,
                                      self._tx_bw_hz, self._tx_atten_db)
        if not ok:
            self._dev.stop()
            raise TxEngineError("TX config read-back mismatch at START: " + report)
        rb = self._dev.readback()
        log("READY tx_running=true source_index=%d burst_sha=%s tx_scale=1.0 "
            "sample_rate_readback=%d tx_lo_readback=%d tx_bw_readback=%d "
            "tx_atten_readback=%.3f"
            % (sample["source_index"], self._current["burst_sha"],
               rb["sample_rate"], rb["tx_lo"], rb["tx_bw"], rb["tx_atten"]))
        return {
            "payload_sha_pre": self._current["payload_sha_pre"],
            "payload_sha_post": self._current["burst_sha"],
            "burst_sha": self._current["burst_sha"],
            "tx_scale": 1.0,
            "sample_rate_readback": rb["sample_rate"],
            "tx_lo_readback": rb["tx_lo"],
            "tx_bw_readback": rb["tx_bw"],
            "tx_atten_readback": rb["tx_atten"],
            "tx_running": True,
        }

    def on_captured(self, session, sample):
        stop_ok = self._dev.stop()
        restore_ok = self._dev.restore()
        ok = stop_ok and restore_ok
        log("STOPPED source_index=%d tx_restore_ok=%s stop_ok=%s restore_ok=%s"
            % (sample["source_index"], "true" if ok else "false",
               "true" if stop_ok else "false", "true" if restore_ok else "false"))
        self._current = None
        return {"tx_restore_ok": ok}

    def on_abort(self, session, reason):
        log("ABORT received reason=%s" % reason)

    def emergency_stop(self):
        self._dev.stop()
        self._dev.restore()


# ---------------------------------------------------------------------------
# Independent watchdog: while the TX is running, if no message for > 2 s, stop TX.
# ---------------------------------------------------------------------------
class Watchdog(threading.Thread):
    def __init__(self, engine, timeout_ms=WATCHDOG_TIMEOUT_MS):
        super().__init__(daemon=True, name="fix1v2-watchdog")
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
# serve_one: run one accepted connection through the protocol session.
# ---------------------------------------------------------------------------
def serve_one(engine, conn):
    session = proto.PcTxServerSession(engine, conn)
    session.serve()


# ---------------------------------------------------------------------------
# Simulated-device control-flow test (in-process, 127.0.0.1, mock TX).
# ---------------------------------------------------------------------------
def _make_client(server_port):
    c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    c.settimeout(proto.DEFAULT_MESSAGE_TIMEOUT_MS / 1000.0)
    c.connect(("127.0.0.1", server_port))
    return c


def _client_send(c, obj):
    proto.send_frame(c, obj)


def _client_recv(c):
    return proto.recv_frame(c)


def run_mock_control_flow(frozen_dir, input_kind=INPUT_KIND, n_frames=24):
    """Spin a mock-TX server on 127.0.0.1, drive a mock CLIENT through the full
    HELLO -> HELLO_ACK -> PREPARE -> PREPARED -> START -> READY -> CAPTURED -> STOPPED
    cycle for every frame, and return a list of (name, ok, detail) checks.

    This is the G4 acceptance test: a simulated device exercises the COMPLETE control
    flow with real frozen burst bytes, no hardware.  It proves the provenance contract
    payload_sha_pre == payload_sha_post == burst_sha == fr.burst_sha256, tx_scale == 1.0,
    tx_running == true on READY, tx_restore_ok == true on STOPPED."""
    checks = []

    manifest = PublicProtocolManifest(frozen_dir)
    engine = PublicProtocolTxEngine(
        MockTxDevice(), frozen_dir, input_kind, DEFAULT_TX_BW_HZ, DEFAULT_TX_ATTEN_DB)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    serve_error = []

    def _serve():
        try:
            conn, _ = server.accept()
            serve_one(engine, conn)
        except Exception as e:  # noqa: BLE001
            serve_error.append(e)
        finally:
            try:
                server.close()
            except OSError:
                pass

    t = threading.Thread(target=_serve, daemon=True)
    t.start()

    session_id = "radioml-independent-rx"
    run_nonce = "nonce-test"
    manifest_sha = manifest.sha256()

    def common(tp):
        return {"type": tp, "protocol": proto.PROTOCOL_VERSION,
                "session_id": session_id, "run_nonce": run_nonce,
                "manifest_sha256": manifest_sha}

    c = _make_client(port)
    try:
        # HELLO -> HELLO_ACK
        _client_send(c, dict(common("HELLO"),
                             input_kind=input_kind,
                             sample_rate=DEFAULT_SAMPLE_RATE_HZ,
                             center_hz=DEFAULT_CENTER_HZ,
                             target_rms=2048.0))
        ack = _client_recv(c)
        checks.append(("HELLO_ACK type", ack.get("type") == "HELLO_ACK", ack.get("type")))
        checks.append(("HELLO_ACK configuration_verified",
                       ack.get("configuration_verified") is True, str(ack.get("configuration_verified"))))
        checks.append(("HELLO_ACK tx_atten_db", abs(float(ack.get("tx_atten_db", 0)) - DEFAULT_TX_ATTEN_DB) < 0.5,
                       str(ack.get("tx_atten_db"))))

        cycle_ok = True
        cycle_detail = ""
        for src in sorted(manifest.rows):
            row = manifest.rows[src]
            expected_sha = row["burst_sha256"]

            # PREPARE -> PREPARED
            _client_send(c, dict(common("PREPARE"), source_index=src,
                                 file_name=row["file_name"], payload_sha_pre=expected_sha))
            prep = _client_recv(c)
            if prep.get("type") != "PREPARED":
                cycle_ok = False; cycle_detail = "PREPARED type=%s src=%d" % (prep.get("type"), src); break
            if (prep.get("payload_sha_pre") != expected_sha or
                    prep.get("payload_sha_post") != expected_sha or
                    prep.get("burst_sha") != expected_sha):
                cycle_ok = False; cycle_detail = "PREPARED sha mismatch src=%d" % src; break
            if abs(float(prep.get("tx_scale", 0)) - 1.0) > 1e-9:
                cycle_ok = False; cycle_detail = "PREPARED tx_scale=%s src=%d" % (prep.get("tx_scale"), src); break

            # START -> READY
            _client_send(c, dict(common("START"), source_index=src, file_name=row["file_name"]))
            ready = _client_recv(c)
            if ready.get("type") != "READY":
                cycle_ok = False; cycle_detail = "READY type=%s src=%d" % (ready.get("type"), src); break
            if (ready.get("burst_sha") != expected_sha or
                    ready.get("payload_sha_pre") != expected_sha or
                    ready.get("payload_sha_post") != expected_sha):
                cycle_ok = False; cycle_detail = "READY sha mismatch src=%d" % src; break
            if abs(float(ready.get("tx_scale", 0)) - 1.0) > 1e-9:
                cycle_ok = False; cycle_detail = "READY tx_scale=%s src=%d" % (ready.get("tx_scale"), src); break
            if ready.get("tx_running") is not True:
                cycle_ok = False; cycle_detail = "READY tx_running=%s src=%d" % (ready.get("tx_running"), src); break
            if ready.get("sample_rate_readback") != DEFAULT_SAMPLE_RATE_HZ:
                cycle_ok = False; cycle_detail = "READY sample_rate_readback=%s src=%d" % (ready.get("sample_rate_readback"), src); break

            # CAPTURED -> STOPPED
            _client_send(c, dict(common("CAPTURED"), source_index=src, file_name=row["file_name"]))
            stopped = _client_recv(c)
            if stopped.get("type") != "STOPPED":
                cycle_ok = False; cycle_detail = "STOPPED type=%s src=%d" % (stopped.get("type"), src); break
            if stopped.get("tx_restore_ok") is not True:
                cycle_ok = False; cycle_detail = "STOPPED tx_restore_ok=%s src=%d" % (stopped.get("tx_restore_ok"), src); break

        checks.append(("full cycle %d frames" % n_frames, cycle_ok, cycle_detail))

        # ABORT -> server exits cleanly
        _client_send(c, dict(common("ABORT"), reason="board_done"))
        # (server closes; no response to ABORT)
    finally:
        try:
            c.close()
        except OSError:
            pass
        t.join(timeout=5.0)

    checks.append(("server exited cleanly", not serve_error,
                   str(serve_error[0]) if serve_error else ""))
    checks.append(("TX stopped after ABORT", not engine.tx_running(), ""))
    return checks


# ---------------------------------------------------------------------------
# Self-test (--self-test): protocol provenance + a synthetic 2-frame full cycle.
# ---------------------------------------------------------------------------
def _make_synthetic_fixture(dir_path, n=24):
    """Write a synthetic n-row public-protocol fixture (manifest + deterministic burst
    bytes) for the self-test.  The bytes are only hashed/length-checked (never decoded),
    so any deterministic content is fine."""
    rows = []
    for src in range(1, n + 1):
        burst = bytearray()
        for k in range(TOTAL_BURST_COMPLEX):
            i = (src * 1000 + k) & 0xFFFF
            q = (src * 2000 + k * 3 + 1) & 0xFFFF
            burst += bytes([i & 0xFF, (i >> 8) & 0xFF,
                            q & 0xFF, (q >> 8) & 0xFF])
        fn = "%d.burst.i16" % src
        with open(os.path.join(dir_path, fn), "wb") as f:
            f.write(bytes(burst))
        rows.append((src, fn, hashlib.sha256(bytes(burst)).hexdigest()))
    lines = [MANIFEST_HEADER]
    for src, fn, sha in rows:
        lines.append("selftest-fixture\tv1\t%d\t%d\tSELFTEST\t%d\t%s\t%s\t%s\t%s"
                     % (src, src - 1, 3000000 + src - 1, fn, sha, sha, sha))
    with open(os.path.join(dir_path, MANIFEST_NAME), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return rows


def run_self_test():
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))
        log("SELF-TEST %-40s %s%s"
            % (name, "PASS" if ok else "FAIL", (" -- " + detail) if detail else ""))

    # (a) protocol module provenance + frozen constants.
    check("protocol module from host_tools",
          os.path.basename(os.path.dirname(getattr(proto, "__file__", ""))) == "host_tools",
          getattr(proto, "__file__", ""))
    check("protocol constants frozen",
          proto.PROTOCOL_VERSION == 1 and proto.DEFAULT_PORT == 39010 and
          proto.MAX_MESSAGE_BYTES == (1 << 20) and proto.WATCHDOG_TIMEOUT_MS <= 2000,
          "protocol=%d port=%d max=%d watchdog_ms=%d"
          % (proto.PROTOCOL_VERSION, proto.DEFAULT_PORT,
             proto.MAX_MESSAGE_BYTES, proto.WATCHDOG_TIMEOUT_MS))

    # (b) synthetic 24-frame fixture + engine provenance unit checks.
    tmp = tempfile.mkdtemp(prefix=".fix1v2_pc_tx_selftest_", dir=_HERE)
    try:
        rows = _make_synthetic_fixture(tmp, n=24)
        manifest = PublicProtocolManifest(tmp)
        check("synthetic manifest 24 rows", len(manifest.rows) == 24, "")

        eng = PublicProtocolTxEngine(MockTxDevice(), tmp, INPUT_KIND,
                                     DEFAULT_TX_BW_HZ, DEFAULT_TX_ATTEN_DB)
        eng._manifest = manifest
        eng._center_hz = DEFAULT_CENTER_HZ
        eng._sample_rate = DEFAULT_SAMPLE_RATE_HZ
        eng._dev.open()
        eng._dev.configure(DEFAULT_CENTER_HZ, DEFAULT_SAMPLE_RATE_HZ,
                           DEFAULT_TX_BW_HZ, DEFAULT_TX_ATTEN_DB)
        prep = eng.on_prepare(None, {"source_index": 1, "file_name": "1.burst.i16",
                                     "payload_sha_pre": rows[0][2]})
        check("engine on_prepare as-is provenance",
              prep["payload_sha_post"] == rows[0][2] and
              prep["burst_sha"] == rows[0][2] and prep["tx_scale"] == 1.0,
              "sha=%s tx_scale=%s" % (prep["burst_sha"][:12], prep["tx_scale"]))
        ready = eng.on_start(None, {"source_index": 1, "file_name": "1.burst.i16"})
        check("engine on_start tx_running + as-is",
              ready["tx_running"] is True and ready["tx_scale"] == 1.0 and
              ready["burst_sha"] == rows[0][2], "")
        check("mock device is running", eng.tx_running(), "")
        stopped = eng.on_captured(None, {"source_index": 1, "file_name": "1.burst.i16"})
        check("engine on_captured tx_restore_ok",
              stopped["tx_restore_ok"] is True, "")
        check("mock device stopped after captured", not eng.tx_running(), "")

        # (c) full in-process mock control flow over 127.0.0.1 (24 frames).
        flow_checks = run_mock_control_flow(tmp, INPUT_KIND, n_frames=24)
        for name, ok, detail in flow_checks:
            check("mock control flow: " + name, ok, detail)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    all_ok = all(c[1] for c in checks)
    log("SELF-TEST %s (%d/%d checks)"
        % ("PASS" if all_ok else "FAIL",
           sum(1 for c in checks if c[1]), len(checks)))
    return 0 if all_ok else 1


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="pc_tx_sdr_fix10_public.py",
        description="fix1(+fix1v2) public-protocol PC TX service (real dual-SDR, TX-only).")
    p.add_argument("--listen", default="0.0.0.0:%d" % DEFAULT_PORT,
                   help="bind host:port (default 0.0.0.0:%d)" % DEFAULT_PORT)
    p.add_argument("--tx-uri", default="",
                   help="libiio URI of the PC's TX SDR (REQUIRED unless --mock)")
    p.add_argument("--frozen-dir", default="",
                   help="frozen public-protocol tx_package dir (manifest + 24 bursts)")
    p.add_argument("--input-kind", default=INPUT_KIND)
    p.add_argument("--center", type=int, default=DEFAULT_CENTER_HZ,
                   help="fallback center Hz (HELLO is authoritative)")
    p.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE_HZ,
                   help="fallback sample rate (HELLO is authoritative)")
    p.add_argument("--tx-bw", type=int, default=DEFAULT_TX_BW_HZ)
    p.add_argument("--tx-atten", type=float, default=DEFAULT_TX_ATTEN_DB,
                   help="TX attenuation dB (<= -40 recommended; never above -40)")
    p.add_argument("--rf-path", default="",
                   help="must be 'direct-cable' to authorize real RF TX")
    p.add_argument("--mock", action="store_true",
                   help="use a simulated TX device (no libiio, no RF)")
    p.add_argument("--self-test", action="store_true",
                   help="run the startup self-test and exit (no device, no RF)")
    return p.parse_args(argv)


def _parse_listen(spec):
    if ":" in spec:
        host, _, port = spec.rpartition(":")
        return host or "0.0.0.0", int(port)
    return "0.0.0.0", int(spec)


def _validate_serve_args(args):
    if not args.frozen_dir:
        return "--frozen-dir is required in serve mode"
    if not args.mock and not args.tx_uri:
        return "--tx-uri is required in serve mode (or pass --mock)"
    if not args.mock and args.rf_path != "direct-cable":
        return ("--rf-path must be 'direct-cable' (50-ohm SMA coax, no antenna, "
                "no amplifier) to authorize real RF TX; got '%s'" % args.rf_path)
    if args.tx_atten > -40.0:
        return "--tx-atten %.3f exceeds the -40 dB safety ceiling; refusing" % args.tx_atten
    return None


def main(argv):
    args = parse_args(argv)

    if args.self_test:
        return run_self_test()

    err = _validate_serve_args(args)
    if err:
        log_err(err)
        return 1

    host, port = _parse_listen(args.listen)

    device = MockTxDevice(args.tx_uri or "mock:public-protocol") if args.mock \
        else PlutoTxDevice(args.tx_uri)
    engine = PublicProtocolTxEngine(device, args.frozen_dir, args.input_kind,
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

    log("listening on %s:%d frozen_dir=%s input_kind=%s tx_bw=%d tx_atten=%.2f "
        "mock=%s"
        % (host, port, args.frozen_dir, args.input_kind, args.tx_bw, args.tx_atten,
           "true" if args.mock else "false"))

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
    primary_error = None
    cleanup_error = None
    try:
        serve_one(engine, conn)
    except proto.ProtocolError as e:
        primary_error = "protocol violation: %s" % e
        log_err(primary_error)
        rc = 1
    except (TxEngineError, ManifestError) as e:
        primary_error = "engine failure: %s" % e
        log_err(primary_error)
        rc = 1
    except (OSError, ConnectionError) as e:
        primary_error = "connection error: %s" % e
        log_err(primary_error)
        rc = 1
    except KeyboardInterrupt:
        primary_error = "interrupted (Ctrl+C)"
        log("interrupted (Ctrl+C); stopping TX")
        rc = 130
    finally:
        for what, fn in (("watchdog shutdown", wd.shutdown),
                         ("engine emergency stop", engine.emergency_stop),
                         ("conn close", conn.close),
                         ("server close", server.close)):
            try:
                fn()
            except Exception as e:
                if cleanup_error is None:
                    cleanup_error = "%s: %s" % (what, e)
                log_err("cleanup %s failed (non-fatal): %s" % (what, e))
    if cleanup_error is not None:
        log_err("cleanup error (did not mask primary): %s" % cleanup_error)
    log("session ended; TX stopped%s"
        % ((" (primary=%s)" % primary_error) if primary_error else ""))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
