#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pc_tx_blind_clean.py -- fix10class24-dualsdr-blind-clean1 PC-side TX service.

The Windows PC owns the TX ADALM-Pluto and transmits a PURE-modulated 24-class
RadioML2018.01A clean waveform CYCLICALLY over 50-ohm coax; the board owns the RX
Pluto and classifies it with ONLY the received IQ + the frozen BF16 model.  The two
ends exchange ONLY control messages + identity over TCP (never real-time IQ, never an
RX device on this side, never the class).

This process is the SERVER peer of the board's control-channel CLIENT.  Protocol
(frozen by contract/blind_rx_sampling_contract.json):
    HELLO -> HELLO_ACK -> [TRANSMIT -> TX_READY -> (board captures+infers) ->
    CAPTURED -> CAPTURED_ACK] x25 -> STOP -> STOP_ACK
  * wire = [uint32 big-endian byte length][UTF-8 JSON]  (port 39010)
  * source_index 0 = negative control (TX off, tx_active=false, file_sha256="")
  * source_index 1..24 = waveform ordinal; the class NEVER crosses toward the board
    (the source_index -> class mapping lives only in the PC's blind_tx_manifest.tsv).

TX convention: each 1024-complex CI16 payload (<source_index>.i16) is pushed into a
cyclic iio.Buffer, so the board's RX always sees a full period at arbitrary phase.
The PC NEVER applies a preamble/tail/training frame, NEVER re-derives a per-class
scale (the payloads are already quantized with the single frozen scale S), and NEVER
reads the class to choose a waveform.

Safety: TX is configured to <= -40 dB (hard ceiling) only on a legal TRANSMIT; a dead
connection can never leave the TX transmitting because the recv loop runs with a <= 2 s
message timeout and stops TX on every timeout / error / disconnect path.

Run (isolated mode so no same-name module is picked up from CWD):
    D:\\radioconda\\python.exe -I host_tools\\pc_tx_blind_clean.py ^
        --listen 0.0.0.0:39010 --tx-uri "<PC_TX_URI>" --tx-dir "<blind tx package>"

Self-test (no device / no RF; framing + manifest + state machine):
    D:\\radioconda\\python.exe -I host_tools\\pc_tx_blind_clean.py --self-test
"""
from __future__ import annotations

import argparse
import array
import ctypes.util as _ctu
import hashlib
import json
import os
import socket
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# libiio DLL resolution + monkeypatch (must precede `import iio`).  radioconda
# pylibiio builds its CDLL with use_last_error=True, so the only reliable fix on
# Windows is to patch ctypes.util.find_library before the first `import iio`.
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

try:
    import iio  # noqa: E402  (now loads radioconda 0.26)
    HAS_IIO = True
except Exception:  # pragma: no cover - self-test / WSL python without libiio
    iio = None
    HAS_IIO = False

# ---------------------------------------------------------------------------
# Frozen constants (authority: contract/blind_rx_sampling_contract.json + headers)
# ---------------------------------------------------------------------------
DEFAULT_PORT = 39010
MAX_MESSAGE_BYTES = 1 << 20
MESSAGE_TIMEOUT_S = 2.0            # <= 2 s (watchdog: dead connection never leaves TX on)
SAFE_TX_ATTEN_DB = -89.75          # max-safe TX attenuation floor (pluto_tx.hpp)
CENTER_HZ = 2400000000
SAMPLE_RATE = 2560000
TX_BW_HZ = 18000000
TX_ATTEN_DB = -40.0                # hard ceiling (never > -40)
N_COMPLEX = 1024                   # one clean waveform period

TOKEN = "M29-RML24-FIX10CLASS24-DUALSDR-BLIND-CLEAN1-PC-TX"

# blind_tx_manifest.tsv columns (authority: scripts/radioml_blind_clean_contract.py)
MANIFEST_HEADER = [
    "source_index", "class_index", "class_name", "seed", "tx_payload_file",
    "tx_payload_sha256", "original_sha256", "peak_abs", "max_lround_abs", "clip",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class TxServiceError(Exception):
    pass


# ---------------------------------------------------------------------------
# wire framing (uint32 BE length prefix + UTF-8 JSON)
# ---------------------------------------------------------------------------
def recv_frame(conn: socket.socket) -> dict:
    """Read one length-prefixed JSON frame.  Raises on timeout / oversize / EOF."""
    hdr = _recv_exact(conn, 4)
    ln = (hdr[0] << 24) | (hdr[1] << 16) | (hdr[2] << 8) | hdr[3]
    if ln > MAX_MESSAGE_BYTES:
        raise TxServiceError("oversize message %d > %d" % (ln, MAX_MESSAGE_BYTES))
    body = _recv_exact(conn, ln)
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise TxServiceError("bad JSON: %s" % e)


def _recv_exact(conn: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise TxServiceError("peer closed connection")
        buf.extend(chunk)
    return bytes(buf)


def send_frame(conn: socket.socket, obj: dict) -> None:
    body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_MESSAGE_BYTES:
        raise TxServiceError("outgoing message exceeds MAX_MESSAGE_BYTES")
    ln = len(body)
    conn.sendall(bytes([(ln >> 24) & 0xFF, (ln >> 16) & 0xFF,
                        (ln >> 8) & 0xFF, ln & 0xFF]) + body)


# ---------------------------------------------------------------------------
# manifest (source_index -> payload file + sha).  Class is NOT consumed by TX.
# ---------------------------------------------------------------------------
def load_manifest(tx_dir: Path) -> dict:
    manifest = tx_dir / "blind_tx_manifest.tsv"
    if not manifest.is_file():
        raise TxServiceError("blind_tx_manifest.tsv not found in %s" % tx_dir)
    lines = manifest.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise TxServiceError("empty manifest")
    header = lines[0].rstrip("\n").split("\t")
    if header != MANIFEST_HEADER:
        raise TxServiceError("manifest header mismatch (got %d cols)" % len(header))
    idx = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        if len(f) != len(MANIFEST_HEADER):
            raise TxServiceError("manifest line not %d cols: %r"
                                 % (len(MANIFEST_HEADER), ln))
        sid = int(f[0])
        fname = f[4]
        psha = f[5]
        p = tx_dir / fname
        if not p.is_file():
            raise TxServiceError("payload missing: %s" % p)
        if sha256_file(p) != psha:
            raise TxServiceError("payload SHA mismatch for %s" % fname)
        idx[sid] = {"file_name": fname, "sha256": psha, "path": p}
    if sorted(idx) != list(range(1, 25)):
        raise TxServiceError("manifest source_index must be exactly 1..24")
    return idx


# ---------------------------------------------------------------------------
# TX device abstraction (real libiio / null for self-test)
# ---------------------------------------------------------------------------
class TxDevice:
    """libiio cyclic TX of a 1024-complex CI16 payload.  RX-free (no rx channel)."""

    def __init__(self, uri: str):
        if not HAS_IIO:
            raise TxServiceError("pylibiio not importable (radioconda 0.26 required)")
        self.uri = uri
        self._ctx = None
        self._phy = None
        self._tx_dma = None
        self._tx_ctrl = None
        self._tx_lo = None
        self._tx_i = None
        self._tx_q = None
        self._txbuf = None
        self._saved = {}
        self._open_device()

    def _rd_ll(self, chan, attr):
        return int(chan.attrs[attr].value)

    def _wr(self, chan, attr, val):
        chan.attrs[attr].value = val

    def _open_device(self):
        try:
            self._ctx = iio.Context(self.uri)
        except OSError as e:
            raise TxServiceError("cannot open TX SDR '%s': %s" % (self.uri, e))
        self._phy = self._ctx.find_device("ad9361-phy")
        self._tx_dma = self._ctx.find_device("cf-ad9361-dds-core-lpc")
        if self._phy is None or self._tx_dma is None:
            raise TxServiceError("missing ad9361-phy / cf-ad9361-dds-core-lpc")
        self._tx_ctrl = self._phy.find_channel("voltage0", True)
        self._tx_lo = self._phy.find_channel("altvoltage1", True)
        self._tx_i = self._tx_dma.find_channel("voltage0", True)
        self._tx_q = self._tx_dma.find_channel("voltage1", True)
        if None in (self._tx_ctrl, self._tx_lo, self._tx_i, self._tx_q):
            raise TxServiceError("missing TX channel")
        self._tx_i.enabled = True
        self._tx_q.enabled = True
        # Snapshot pre-run state so CAPTURED/STOP can restore it.
        try:
            self._saved = {
                "tx_lo": self._rd_ll(self._tx_lo, "frequency"),
                "tx_sample_rate": self._rd_ll(self._tx_ctrl, "sampling_frequency"),
                "tx_bw": self._rd_ll(self._tx_ctrl, "rf_bandwidth"),
                "tx_atten": float(self._tx_ctrl.attrs["hardwaregain"].value),
                "loopback": int(self._phy.debug_attrs["loopback"].value),
            }
        except Exception:
            self._saved = {}

    def configure(self):
        # Fixed order (pluto_tx.hpp prepare()): safe floor atten first, then LO /
        # sample rate / bw / loopback, then ramp to the working atten.
        self._wr(self._tx_ctrl, "hardwaregain", "%.2f" % SAFE_TX_ATTEN_DB)
        self._wr(self._tx_lo, "frequency", str(CENTER_HZ))
        self._wr(self._tx_ctrl, "sampling_frequency", str(SAMPLE_RATE))
        self._wr(self._tx_ctrl, "rf_bandwidth", str(TX_BW_HZ))
        self._phy.debug_attrs["loopback"].value = "0"    # external RF (coax)
        self._wr(self._tx_ctrl, "hardwaregain", "%.2f" % TX_ATTEN_DB)

    def start(self, payload_bytes: bytes):
        self.stop()
        if len(payload_bytes) != 2 * N_COMPLEX * 2:
            raise TxServiceError("payload byte size %d != %d"
                                 % (len(payload_bytes), 2 * N_COMPLEX * 2))
        arr = array.array("h")
        arr.frombytes(payload_bytes)
        if arr.itemsize != 2 or len(arr) != 2 * N_COMPLEX:
            raise TxServiceError("payload byte/complex mismatch before TX")
        i_bytes = bytearray(arr[0::2].tobytes())
        q_bytes = bytearray(arr[1::2].tobytes())
        self.configure()
        self._txbuf = iio.Buffer(self._tx_dma, N_COMPLEX, cyclic=True)
        # raw=False -> iio_channel_write -> convert_inverse (same 12-bit path as C++).
        self._tx_i.write(self._txbuf, i_bytes, raw=False)
        self._tx_q.write(self._txbuf, q_bytes, raw=False)
        self._txbuf.push(N_COMPLEX)

    def stop(self):
        buf = self._txbuf
        self._txbuf = None
        if buf is None:
            return True
        try:
            buf.cancel()
        except Exception:
            return False
        del buf          # drop last ref -> iio_buffer_destroy stops the cyclic DMA
        return self._txbuf is None

    def restore(self):
        if not self._saved or self._ctx is None:
            return False
        try:
            self._tx_lo.attrs["frequency"].value = str(self._saved["tx_lo"])
            self._tx_ctrl.attrs["sampling_frequency"].value = \
                str(self._saved["tx_sample_rate"])
            self._tx_ctrl.attrs["hardwaregain"].value = "%.2f" % self._saved["tx_atten"]
            self._phy.debug_attrs["loopback"].value = str(self._saved["loopback"])
            if self._saved["tx_bw"] != 0:
                self._tx_ctrl.attrs["rf_bandwidth"].value = str(self._saved["tx_bw"])
        except Exception:
            return False
        return True

    def close(self):
        self.stop()
        if self._ctx is not None:
            self._ctx = None


class NullTxDevice:
    """Self-test stub: records start/stop, never touches libiio."""
    def __init__(self):
        self.running = False
        self.last_payload = None
        self.configured = False

    def configure(self):
        self.configured = True

    def start(self, payload_bytes: bytes):
        self.running = True
        self.last_payload = payload_bytes

    def stop(self):
        self.running = False
        return True

    def restore(self):
        return True

    def close(self):
        self.stop()


# ---------------------------------------------------------------------------
# Blind TX session state machine (testable without libiio / sockets)
# ---------------------------------------------------------------------------
class BlindTxSession:
    """Implements the PC side of HELLO/TRANSMIT/CAPTURED/STOP against one board."""

    def __init__(self, manifest: dict, device):
        self.manifest = manifest
        self.dev = device
        self.session_id = None
        self.run_nonce = None
        self.measurements = None
        self.hellod = False

    def _reply(self, obj):
        return obj

    def handle(self, msg: dict):
        mtype = msg.get("type")
        if mtype == "hello":
            return self._on_hello(msg)
        if mtype == "transmit":
            return self._on_transmit(msg)
        if mtype == "captured":
            return self._on_captured(msg)
        if mtype == "stop":
            return self._on_stop(msg)
        raise TxServiceError("unknown message type %r" % mtype)

    def _on_hello(self, msg):
        if msg.get("protocol_version") != 1:
            raise TxServiceError("unsupported protocol_version")
        sid = msg.get("session_id")
        rn = msg.get("run_nonce")
        meas = msg.get("measurements")
        if not isinstance(sid, str) or not isinstance(rn, str) or \
                not isinstance(meas, (int, float)):
            raise TxServiceError("hello missing session_id/run_nonce/measurements")
        if int(meas) != 25:
            raise TxServiceError("hello measurements must be 25 (1 negative + 24)")
        self.session_id = sid
        self.run_nonce = rn
        self.measurements = int(meas)
        self.hellod = True
        return {"session_id": sid, "run_nonce": rn, "measurements": self.measurements,
                "ok": True}

    def _on_transmit(self, msg):
        if not self.hellod:
            raise TxServiceError("transmit before hello")
        sid = msg.get("source_index")
        if not isinstance(sid, (int, float)):
            raise TxServiceError("transmit missing source_index")
        sid = int(sid)
        if sid == 0:
            self.dev.stop()
            return {"source_index": 0, "tx_active": False, "file_sha256": ""}
        if sid not in self.manifest:
            raise TxServiceError("source_index %d not in manifest" % sid)
        row = self.manifest[sid]
        payload = row["path"].read_bytes()
        self.dev.start(payload)
        return {"source_index": sid, "tx_active": True,
                "file_sha256": row["sha256"]}

    def _on_captured(self, msg):
        sid = msg.get("source_index")
        self.dev.stop()
        return {"source_index": int(sid) if isinstance(sid, (int, float)) else 0}

    def _on_stop(self, msg):
        self.dev.stop()
        self.dev.restore()
        return {}


def serve(listen_host: str, port: int, manifest: dict, device) -> int:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((listen_host, port))
    srv.listen(1)
    print("%s LISTENING host=%s port=%d" % (TOKEN, listen_host, port), flush=True)

    conn, addr = srv.accept()
    print("%s CONNECTED peer=%s:%d" % (TOKEN, addr[0], addr[1]), flush=True)
    conn.settimeout(MESSAGE_TIMEOUT_S)
    session = BlindTxSession(manifest, device)
    try:
        while True:
            try:
                msg = recv_frame(conn)
            except socket.timeout:
                device.stop()
                print("%s TIMEOUT no-message-for-%.1fs -> TX stopped"
                      % (TOKEN, MESSAGE_TIMEOUT_S), flush=True)
                break
            except TxServiceError as e:
                print("%s PROTOCOL_ERROR %s" % (TOKEN, e), flush=True)
                device.stop()
                break
            try:
                reply = session.handle(msg)
                send_frame(conn, reply)
                if msg.get("type") == "stop":
                    break
            except TxServiceError as e:
                print("%s HANDLE_ERROR %s" % (TOKEN, e), flush=True)
                device.stop()
                break
    finally:
        device.stop()
        device.restore()
        try:
            conn.close()
        except OSError:
            pass
        srv.close()
    print("%s DONE" % TOKEN, flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listen", default="0.0.0.0:39010")
    ap.add_argument("--tx-uri", default="")
    ap.add_argument("--tx-dir", default="")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    host, _, port_s = args.listen.rpartition(":")
    if not host or not port_s.isdigit():
        raise SystemExit("ERROR: --listen must be host:port")
    port = int(port_s)
    if not args.tx_uri:
        raise SystemExit("ERROR: --tx-uri=<libiio URI of PC TX SDR> is required")
    if not args.tx_dir:
        raise SystemExit("ERROR: --tx-dir=<blind TX package dir> is required")

    manifest = load_manifest(Path(args.tx_dir))
    device = TxDevice(args.tx_uri)
    try:
        return serve(host, port, manifest, device)
    finally:
        device.close()


# ---------------------------------------------------------------------------
# self-test (no device / no RF)
# ---------------------------------------------------------------------------
def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-48s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))

    # framing roundtrip
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        a, b = socket.socketpair()
        try:
            send_frame(a, {"type": "hello", "measurements": 25, "ok": True})
            obj = recv_frame(b)
            check("frame roundtrip (uint32 BE + JSON)",
                  obj == {"type": "hello", "measurements": 25, "ok": True})
        finally:
            a.close(); b.close()

    # manifest parsing (build a minimal 24-row manifest in a temp dir)
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        lines = ["\t".join(MANIFEST_HEADER)]
        for s in range(1, 25):
            fname = "%d.i16" % s
            payload = bytes(2 * N_COMPLEX * 2)
            (d / fname).write_bytes(payload)
            psha = sha256_file(d / fname)
            lines.append("\t".join([str(s), "0", "QPSK", "3000000", fname, psha,
                                    "0" * 64, "1.0", "1600", "0"]))
        (d / "blind_tx_manifest.tsv").write_text("\n".join(lines) + "\n",
                                                 encoding="utf-8")
        idx = load_manifest(d)
        check("manifest: 24 source_index parsed", sorted(idx) == list(range(1, 25)))

        dev = NullTxDevice()
        sess = BlindTxSession(idx, dev)
        ack = sess.handle({"type": "hello", "protocol_version": 1,
                           "session_id": "blind-abc", "run_nonce": "def",
                           "measurements": 25})
        check("hello -> hello_ack echoes identity + ok",
              ack == {"session_id": "blind-abc", "run_nonce": "def",
                      "measurements": 25, "ok": True})
        ready = sess.handle({"type": "transmit", "source_index": 1})
        check("transmit(1) -> tx_active=true + sha", ready["tx_active"] is True
              and ready["file_sha256"] == idx[1]["sha256"] and dev.running)
        neg = sess.handle({"type": "transmit", "source_index": 0})
        check("transmit(0) -> negative control (tx off, empty sha)",
              neg == {"source_index": 0, "tx_active": False, "file_sha256": ""}
              and not dev.running)
        cap = sess.handle({"type": "captured", "source_index": 0})
        check("captured -> captured_ack echo source_index", cap["source_index"] == 0
              and not dev.running)
        stop = sess.handle({"type": "stop"})
        check("stop -> stop_ack empty object", stop == {})

        # fail-closed: transmit before hello
        dev2 = NullTxDevice()
        sess2 = BlindTxSession(idx, dev2)
        try:
            sess2.handle({"type": "transmit", "source_index": 1})
            check("transmit-before-hello rejected", False)
        except TxServiceError:
            check("transmit-before-hello rejected", True)

        # fail-closed: bad measurements
        dev3 = NullTxDevice()
        sess3 = BlindTxSession(idx, dev3)
        try:
            sess3.handle({"type": "hello", "protocol_version": 1,
                          "session_id": "x", "run_nonce": "y", "measurements": 24})
            check("hello measurements != 25 rejected", False)
        except TxServiceError:
            check("hello measurements != 25 rejected", True)

    all_ok = all(checks)
    print("RADIOML_BLIND_CLEAN1_PC_TX_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
