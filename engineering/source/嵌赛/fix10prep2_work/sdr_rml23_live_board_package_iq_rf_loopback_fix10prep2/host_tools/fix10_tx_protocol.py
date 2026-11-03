#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix10prep2 PC-side TX control protocol (pure Python, iio-free).

This is the PC-side SERVER peer of the board's CLIENT control channel.  It must be
byte-compatible with two C++ headers in the same tree:

  * sdr_adapter/tcp_control_client.hpp        -- uint32 big-endian length-prefixed
                                                 JSON frames + the frozen constants;
  * board_package/iq_pc_tx_board_rx_transfer_fix10.hpp -- the per-message field set
                                                 + the strict per-sample state machine.

Wire format (frozen by the fix10prep2 task book §7):

  [uint32 big-endian byte length][UTF-8 JSON payload]

  * the length counts the JSON payload bytes only (not the 4-byte prefix);
  * a length > MAX_MESSAGE_BYTES is refused fail-closed (connection dropped);
  * every message carries protocol / session_id / run_nonce / manifest_sha256 and is
    validated exactly: a missing field, an unknown field, a wrong type, a duplicate,
    an out-of-order or illegal-state message all fail closed.

This module is pure stdlib so it unit-tests under any Python 3 and is imported by
pc_tx_sdr_fix10.py via importlib.util.spec_from_file_location() -- so `python -I`
isolated mode never silently loads a same-name module from the CWD or another
environment.

Role of the two ends (real dual-SDR topology): the PC owns the TX SDR and never
opens an RX device; the board owns the RX SDR and never opens a TX device.  This
module handles ONLY the control channel; the TX engine (SDR actions) is injected by
the caller through the PcTxServerEngine interface so the protocol stays testable
without libiio.
"""

import json
import socket
import struct

# ---------------------------------------------------------------------------
# Frozen wire-protocol constants (must match sdr_adapter/tcp_control_client.hpp).
# ---------------------------------------------------------------------------
PROTOCOL_VERSION = 1
DEFAULT_PORT = 39010
MAX_MESSAGE_BYTES = 1 << 20          # 1 MiB hard limit
DEFAULT_CONNECT_TIMEOUT_MS = 2000    # all timeouts <= 2 s (task book §7)
DEFAULT_MESSAGE_TIMEOUT_MS = 2000
WATCHDOG_TIMEOUT_MS = 2000           # independent PC watchdog <= 2 s

# Common keys validated on every inbound message (in this exact order, as emitted
# by the board's common_fields()).
COMMON_KEYS = ("type", "protocol", "session_id", "run_nonce", "manifest_sha256")


class ProtocolError(Exception):
    """Fail-closed protocol violation; the peer is disconnected on this."""


def _is_number(v):
    # bool is an int subclass in Python; JSON true/false must NOT satisfy this.
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _as_int(v):
    # Mirrors the C++ Json::as_int() == llround(number).
    return int(round(float(v)))


def _as_number(v):
    return float(v)


def valid_sha64(s):
    """64 lowercase hex (mirrors iqpctbrx::valid_sha64)."""
    if not isinstance(s, str) or len(s) != 64:
        return False
    for c in s:
        if not ("0" <= c <= "9" or "a" <= c <= "f"):
            return False
    return True


# ---------------------------------------------------------------------------
# Frame I/O -- uint32 big-endian length prefix + UTF-8 JSON payload.
# ---------------------------------------------------------------------------

def _recv_exact(sock, n, timeout_ms):
    sock.settimeout(timeout_ms / 1000.0)
    chunks = []
    remaining = n
    while remaining > 0:
        try:
            chunk = sock.recv(remaining)
        except socket.timeout:
            raise ProtocolError("recv timeout (message_timeout_ms)")
        if not chunk:
            raise ProtocolError("peer closed connection")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def send_frame(sock, obj, max_bytes=MAX_MESSAGE_BYTES):
    """Serialize `obj` (a dict) and send it length-prefixed.  Raises ProtocolError on
    an oversize payload."""
    payload = json.dumps(obj, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    if len(payload) > max_bytes:
        raise ProtocolError("outgoing message exceeds max_message_bytes")
    sock.sendall(struct.pack(">I", len(payload)) + payload)


def recv_frame(sock, max_bytes=MAX_MESSAGE_BYTES,
               timeout_ms=DEFAULT_MESSAGE_TIMEOUT_MS):
    """Receive one complete length-prefixed JSON frame.  Handles fragmentation and
    coalescing (extra bytes stay in the kernel buffer for the next call).  Raises
    ProtocolError on timeout / peer close / oversize / malformed JSON."""
    header = _recv_exact(sock, 4, timeout_ms)
    (length,) = struct.unpack(">I", header)
    if length > max_bytes:
        raise ProtocolError(
            "incoming message length %d exceeds max_message_bytes" % length)
    body = _recv_exact(sock, length, timeout_ms)
    try:
        obj = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ProtocolError("JSON parse error: %s" % e)
    return obj


# ---------------------------------------------------------------------------
# Session + message validation (mirrors iq_pc_tx_board_rx_transfer_fix10.hpp).
# ---------------------------------------------------------------------------

class SessionContext:
    """The session identity the board declares in HELLO and repeats on every message."""

    __slots__ = ("session_id", "run_nonce", "manifest_sha256")

    def __init__(self, session_id, run_nonce, manifest_sha256):
        self.session_id = session_id
        self.run_nonce = run_nonce
        self.manifest_sha256 = manifest_sha256


def _validate_exact_fields(obj, expect_keys):
    if not isinstance(obj, dict):
        raise ProtocolError("message is not a JSON object")
    for k in expect_keys:
        if k not in obj:
            raise ProtocolError("missing field '%s'" % k)
    for k in obj:
        if k not in expect_keys:
            raise ProtocolError("unknown field '%s'" % k)


def _validate_common(obj, expected_type, session):
    if not isinstance(obj, dict):
        raise ProtocolError("message is not a JSON object")
    t = obj.get("type")
    if not isinstance(t, str) or t != expected_type:
        raise ProtocolError("wrong message type (expected %s)" % expected_type)
    p = obj.get("protocol")
    if not _is_number(p) or _as_int(p) != PROTOCOL_VERSION:
        raise ProtocolError("protocol version mismatch")
    sid = obj.get("session_id")
    if not isinstance(sid, str) or sid != session.session_id:
        raise ProtocolError("session_id mismatch")
    rn = obj.get("run_nonce")
    if not isinstance(rn, str) or rn != session.run_nonce:
        raise ProtocolError("run_nonce mismatch")
    ms = obj.get("manifest_sha256")
    if not isinstance(ms, str) or ms != session.manifest_sha256:
        raise ProtocolError("manifest_sha256 mismatch")


def _require_integer(v, field):
    if not _is_number(v) or float(v) != round(float(v)):
        raise ProtocolError("%s not an integer" % field)
    return _as_int(v)


def _require_string(v, field, nonempty=False):
    if not isinstance(v, str) or (nonempty and not v):
        raise ProtocolError("%s not a%s string" % (field, " non-empty" if nonempty else ""))
    return v


def _require_sha64(v, field):
    if not valid_sha64(v):
        raise ProtocolError("%s not 64-hex" % field)
    return v


# ---------------------------------------------------------------------------
# Inbound message parsers (client -> server).  Each returns a dict of validated,
# typed fields; each raises ProtocolError on any violation.
# ---------------------------------------------------------------------------

def parse_hello(obj):
    """HELLO establishes the session.  Returns (SessionContext, hello_dict)."""
    expect = COMMON_KEYS + ("input_kind", "sample_rate", "center_hz", "target_rms")
    _validate_exact_fields(obj, expect)
    if not isinstance(obj.get("type"), str) or obj["type"] != "HELLO":
        raise ProtocolError("wrong message type (expected HELLO)")
    p = obj.get("protocol")
    if not _is_number(p) or _as_int(p) != PROTOCOL_VERSION:
        raise ProtocolError("protocol version mismatch")
    sid = _require_string(obj.get("session_id"), "session_id", nonempty=True)
    rn = _require_string(obj.get("run_nonce"), "run_nonce", nonempty=True)
    ms = _require_sha64(obj.get("manifest_sha256"), "manifest_sha256")
    session = SessionContext(sid, rn, ms)
    hello = {
        "input_kind": _require_string(obj.get("input_kind"), "input_kind"),
        "sample_rate": _require_integer(obj.get("sample_rate"), "sample_rate"),
        "center_hz": _require_integer(obj.get("center_hz"), "center_hz"),
        "target_rms": _as_number(obj.get("target_rms")),
    }
    if not _is_number(obj.get("target_rms")):
        raise ProtocolError("target_rms not a number")
    if hello["target_rms"] <= 0.0:
        raise ProtocolError("target_rms not positive")
    return session, hello


def _parse_sample(obj, expected_type, session, with_sha):
    expect = COMMON_KEYS + ("source_index", "file_name", "payload_sha_pre")
    if not with_sha:
        expect = COMMON_KEYS + ("source_index", "file_name")
    _validate_exact_fields(obj, expect)
    _validate_common(obj, expected_type, session)
    sample = {
        "source_index": _require_integer(obj.get("source_index"), "source_index"),
        "file_name": _require_string(obj.get("file_name"), "file_name", nonempty=True),
    }
    if with_sha:
        sample["payload_sha_pre"] = _require_sha64(
            obj.get("payload_sha_pre"), "payload_sha_pre")
    return sample


def parse_prepare(obj, session):
    return _parse_sample(obj, "PREPARE", session, with_sha=True)


def parse_start(obj, session):
    return _parse_sample(obj, "START", session, with_sha=False)


def parse_captured(obj, session):
    return _parse_sample(obj, "CAPTURED", session, with_sha=False)


def parse_abort(obj, session):
    expect = COMMON_KEYS + ("reason",)
    _validate_exact_fields(obj, expect)
    _validate_common(obj, "ABORT", session)
    return {"reason": _require_string(obj.get("reason"), "reason")}


# ---------------------------------------------------------------------------
# Outbound message builders (server -> client).
# ---------------------------------------------------------------------------

def _common(type_, session):
    return {
        "type": type_,
        "protocol": PROTOCOL_VERSION,
        "session_id": session.session_id,
        "run_nonce": session.run_nonce,
        "manifest_sha256": session.manifest_sha256,
    }


def build_hello_ack(session, tx_serial, tx_uri, tx_atten_db, configuration_verified):
    m = _common("HELLO_ACK", session)
    m.update({
        "tx_serial": tx_serial,
        "tx_uri": tx_uri,
        "tx_atten_db": float(tx_atten_db),
        "configuration_verified": bool(configuration_verified),
    })
    return m


def build_prepared(session, source_index, file_name, payload_sha_pre,
                   payload_sha_post, burst_sha, tx_scale, configuration_verified=True):
    m = _common("PREPARED", session)
    m.update({
        "source_index": int(source_index),
        "file_name": file_name,
        "payload_sha_pre": payload_sha_pre,
        "payload_sha_post": payload_sha_post,
        "burst_sha": burst_sha,
        "tx_scale": float(tx_scale),
        "configuration_verified": bool(configuration_verified),
    })
    return m


def build_ready(session, source_index, file_name, payload_sha_pre, payload_sha_post,
                burst_sha, tx_scale, sample_rate_readback, tx_lo_readback,
                tx_bw_readback, tx_atten_readback, tx_running):
    m = _common("READY", session)
    m.update({
        "source_index": int(source_index),
        "file_name": file_name,
        "payload_sha_pre": payload_sha_pre,
        "payload_sha_post": payload_sha_post,
        "burst_sha": burst_sha,
        "tx_scale": float(tx_scale),
        "sample_rate_readback": int(sample_rate_readback),
        "tx_lo_readback": int(tx_lo_readback),
        "tx_bw_readback": int(tx_bw_readback),
        "tx_atten_readback": float(tx_atten_readback),
        "tx_running": bool(tx_running),
    })
    return m


def build_stopped(session, tx_restore_ok):
    m = _common("STOPPED", session)
    m["tx_restore_ok"] = bool(tx_restore_ok)
    return m


# ---------------------------------------------------------------------------
# PcTxServerEngine -- the injected TX-SDR actions.  The protocol layer calls these
# at the state transitions; the engine never sees raw frames, only validated dicts.
#
#   on_hello(session, hello) -> {tx_serial, tx_uri, tx_atten_db, configuration_verified}
#   on_prepare(session, sample) -> {payload_sha_post, burst_sha, tx_scale}
#       -- build + verify the burst (via build_burst_cli); MUST NOT start TX.
#   on_start(session, sample) -> {payload_sha_post, burst_sha, tx_scale,
#       sample_rate_readback, tx_lo_readback, tx_bw_readback, tx_atten_readback,
#       tx_running}
#       -- start cyclic TX with the prepared burst; only here may TX emit.
#   on_captured(session, sample) -> {tx_restore_ok}
#       -- stop TX and restore the TX state.
#   on_abort(session, reason) -> None          -- emergency stop TX.
#   on_activity() -> None                      -- refresh the watchdog timestamp.
#   emergency_stop() -> None                   -- idempotent TX stop (finally / error).
# ---------------------------------------------------------------------------

class PcTxServerSession:
    """PC-side server: drives one board connection through the strict per-sample
    state machine, delegating SDR actions to the injected `engine`.

    Strict single-direction state machine (mirrors the board's header):
        WAIT_HELLO  --HELLO-->    WAIT_PREPARE
        WAIT_PREPARE--PREPARE-->  WAIT_START      (also ABORT)
        WAIT_START  --START-->    WAIT_CAPTURED   (also ABORT)
        WAIT_CAPTURED--CAPTURED-->WAIT_PREPARE    (also ABORT)
    Any other message type in a given state, or a sample identity that does not match
    the in-flight PREPARE, raises ProtocolError (fail-closed).
    """

    _TRANSITIONS = {
        "WAIT_HELLO": ("HELLO",),
        "WAIT_PREPARE": ("PREPARE", "ABORT"),
        "WAIT_START": ("START", "ABORT"),
        "WAIT_CAPTURED": ("CAPTURED", "ABORT"),
    }

    def __init__(self, engine, sock,
                 max_bytes=MAX_MESSAGE_BYTES,
                 message_timeout_ms=DEFAULT_MESSAGE_TIMEOUT_MS):
        self.engine = engine
        self.sock = sock
        self.max_bytes = max_bytes
        self.message_timeout_ms = message_timeout_ms
        self.state = "WAIT_HELLO"
        self.session = None
        self.current_sample = None   # dict(source_index, file_name, payload_sha_pre)

    def serve(self):
        """Run the state machine until the board disconnects, ABORTs, or a fail-closed
        violation occurs.  The TX is stopped (via engine.emergency_stop()) on every
        exit path."""
        try:
            while True:
                msg = recv_frame(self.sock, self.max_bytes, self.message_timeout_ms)
                self.engine.on_activity()
                if not self._dispatch(msg):
                    break
        finally:
            self.engine.emergency_stop()

    def _dispatch(self, msg):
        if not isinstance(msg, dict):
            raise ProtocolError("message is not a JSON object")
        t = msg.get("type")
        if t not in self._TRANSITIONS[self.state]:
            raise ProtocolError(
                "illegal message type %r in state %s" % (t, self.state))

        if t == "HELLO":
            self.session, hello = parse_hello(msg)
            ack = self.engine.on_hello(self.session, hello)
            send_frame(self.sock, build_hello_ack(self.session, **ack),
                       self.max_bytes)
            self.state = "WAIT_PREPARE"
            return True

        # Every non-HELLO message requires an established session.
        if self.session is None:
            raise ProtocolError("message before HELLO")

        if t == "PREPARE":
            sample = parse_prepare(msg, self.session)
            self.current_sample = sample
            prepared = self.engine.on_prepare(self.session, sample)
            send_frame(self.sock,
                       build_prepared(self.session, **sample, **prepared),
                       self.max_bytes)
            self.state = "WAIT_START"
            return True

        if t == "START":
            sample = parse_start(msg, self.session)
            self._require_current_sample(sample)
            ready = self.engine.on_start(self.session, sample)
            send_frame(self.sock, build_ready(self.session, **sample, **ready),
                       self.max_bytes)
            self.state = "WAIT_CAPTURED"
            return True

        if t == "CAPTURED":
            sample = parse_captured(msg, self.session)
            self._require_current_sample(sample)
            stopped = self.engine.on_captured(self.session, sample)
            send_frame(self.sock, build_stopped(self.session, **stopped),
                       self.max_bytes)
            self.current_sample = None
            self.state = "WAIT_PREPARE"
            return True

        if t == "ABORT":
            a = parse_abort(msg, self.session)
            self.engine.on_abort(self.session, a["reason"])
            return False

        raise ProtocolError("unhandled message type %r" % t)

    def _require_current_sample(self, sample):
        if self.current_sample is None:
            raise ProtocolError("START/CAPTURED without an in-flight PREPARE")
        if (sample["source_index"] != self.current_sample["source_index"] or
                sample["file_name"] != self.current_sample["file_name"]):
            raise ProtocolError("sample identity mismatch against in-flight PREPARE")
