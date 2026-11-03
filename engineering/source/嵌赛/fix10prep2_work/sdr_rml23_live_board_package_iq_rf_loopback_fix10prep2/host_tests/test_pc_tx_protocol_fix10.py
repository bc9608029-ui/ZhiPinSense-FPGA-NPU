#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_pc_tx_protocol_fix10.py -- pure-stdlib unittest of fix10_tx_protocol.py.

This is the host-side (WSL) Python counterpart to the C++ protocol test.  It loads the
SAME package module pc_tx_sdr_fix10.py loads -- by absolute path via
importlib.util.spec_from_file_location() -- and never touches libiio, so it runs under
any Python 3 and proves the wire protocol without a device.

Covered (mirrors fix10prep2 task book §7 + §12):
  * frozen constants (uint32 big-endian length prefix, 1 MiB cap, <= 2 s watchdog);
  * frame fragmentation / coalescing / oversize / timeout / peer-close fail-closed;
  * HELLO / PREPARE / START / CAPTURED / ABORT validation (exact fields, unknown field,
    wrong protocol version, session_id / run_nonce / manifest_sha256 mismatch,
    missing source_index, bad 64-hex payload_sha_pre);
  * the strict per-sample state machine (HELLO -> PREPARE -> START -> CAPTURED), with
    illegal transitions, sample-identity mismatch, and duplicate START fail-closed;
  * end-to-end serve() over a real socket pair.
"""

import importlib.util
import os
import socket
import struct
import threading
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROTO_PATH = os.path.normpath(os.path.join(_HERE, "..", "host_tools",
                                            "fix10_tx_protocol.py"))

_spec = importlib.util.spec_from_file_location("fix10_tx_protocol", _PROTO_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load fix10_tx_protocol.py at %s" % _PROTO_PATH)
proto = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(proto)

SID = "sess-0001"
RN = "nonce-0001"
MS = "a" * 64          # valid lowercase 64-hex
BURST_SHA = "b" * 64
POST_SHA = "c" * 64
PRE_SHA = "d" * 64


def _common(type_, sid=SID, rn=RN, ms=MS):
    return {"type": type_, "protocol": 1, "session_id": sid, "run_nonce": rn,
            "manifest_sha256": ms}


def hello_msg(**kw):
    m = _common("HELLO")
    m.update({"input_kind": "radioml-d2-2p56m", "sample_rate": 2560000,
              "center_hz": 2400000000, "target_rms": 2048.0})
    m.update(kw)
    return m


def prepare_msg(**kw):
    m = _common("PREPARE")
    m.update({"source_index": 0, "file_name": "sample_000.ci16",
              "payload_sha_pre": PRE_SHA})
    m.update(kw)
    return m


def start_msg(**kw):
    m = _common("START")
    m.update({"source_index": 0, "file_name": "sample_000.ci16"})
    m.update(kw)
    return m


def captured_msg(**kw):
    m = _common("CAPTURED")
    m.update({"source_index": 0, "file_name": "sample_000.ci16"})
    m.update(kw)
    return m


def abort_msg(**kw):
    m = _common("ABORT")
    m["reason"] = "board_done"
    m.update(kw)
    return m


class FakeEngine:
    """Records callbacks and returns the provenance the protocol splices into each
    reply, so the state machine can be exercised without libiio."""

    def __init__(self):
        self.events = []
        self.hello_ack = {"tx_serial": "1044734c9505000b", "tx_uri": "usb:1.2.3",
                          "tx_atten_db": -40.0, "configuration_verified": True}
        self.prepared = {"payload_sha_post": POST_SHA, "burst_sha": BURST_SHA,
                         "tx_scale": 1.0}
        self.ready = {"payload_sha_pre": PRE_SHA, "payload_sha_post": POST_SHA,
                      "burst_sha": BURST_SHA, "tx_scale": 1.0,
                      "sample_rate_readback": 2560000, "tx_lo_readback": 2400000000,
                      "tx_bw_readback": 18000000, "tx_atten_readback": -40.0,
                      "tx_running": True}
        self.stopped = {"tx_restore_ok": True}

    def on_hello(self, session, hello):
        self.events.append(("hello", session, hello))
        return self.hello_ack

    def on_prepare(self, session, sample):
        self.events.append(("prepare", session, sample))
        return self.prepared

    def on_start(self, session, sample):
        self.events.append(("start", session, sample))
        return self.ready

    def on_captured(self, session, sample):
        self.events.append(("captured", session, sample))
        return self.stopped

    def on_abort(self, session, reason):
        self.events.append(("abort", session, reason))

    def on_activity(self):
        self.events.append(("activity",))

    def emergency_stop(self):
        self.events.append(("emergency_stop",))


class TestConstants(unittest.TestCase):
    def test_frozen_wire_constants(self):
        self.assertEqual(proto.PROTOCOL_VERSION, 1)
        self.assertEqual(proto.DEFAULT_PORT, 39010)
        self.assertEqual(proto.MAX_MESSAGE_BYTES, 1 << 20)
        self.assertLessEqual(proto.WATCHDOG_TIMEOUT_MS, 2000)
        self.assertGreater(proto.DEFAULT_CONNECT_TIMEOUT_MS, 0)
        self.assertLessEqual(proto.DEFAULT_CONNECT_TIMEOUT_MS, 2000)
        self.assertGreater(proto.DEFAULT_MESSAGE_TIMEOUT_MS, 0)
        self.assertLessEqual(proto.DEFAULT_MESSAGE_TIMEOUT_MS, 2000)

    def test_valid_sha64(self):
        self.assertTrue(proto.valid_sha64("a" * 64))
        self.assertFalse(proto.valid_sha64("a" * 63))
        self.assertFalse(proto.valid_sha64("A" * 64))      # uppercase rejected
        self.assertFalse(proto.valid_sha64("g" * 64))      # non-hex
        self.assertFalse(proto.valid_sha64(123))


class TestFrameIo(unittest.TestCase):
    def test_roundtrip(self):
        a, b = socket.socketpair()
        try:
            proto.send_frame(a, {"type": "X", "n": 1})
            self.assertEqual(proto.recv_frame(b), {"type": "X", "n": 1})
        finally:
            a.close(); b.close()

    def test_fragmented_recv(self):
        # Length prefix and body delivered one byte at a time still parse.
        a, b = socket.socketpair()
        try:
            payload = proto.json.dumps({"type": "FRAG"}, separators=(",", ":")).encode()
            frame = struct.pack(">I", len(payload)) + payload
            for byte in frame:
                a.send(bytes([byte]))
            self.assertEqual(proto.recv_frame(b), {"type": "FRAG"})
        finally:
            a.close(); b.close()

    def test_coalesced_recv(self):
        # Two frames in one buffer: first is consumed, second stays for the next call.
        a, b = socket.socketpair()
        try:
            proto.send_frame(a, {"type": "ONE"})
            proto.send_frame(a, {"type": "TWO"})
            self.assertEqual(proto.recv_frame(b), {"type": "ONE"})
            self.assertEqual(proto.recv_frame(b), {"type": "TWO"})
        finally:
            a.close(); b.close()

    def test_oversize_length_rejected(self):
        a, b = socket.socketpair()
        try:
            a.send(struct.pack(">I", proto.MAX_MESSAGE_BYTES + 1))
            with self.assertRaises(proto.ProtocolError):
                proto.recv_frame(b)
        finally:
            a.close(); b.close()

    def test_recv_timeout_fail_closed(self):
        a, b = socket.socketpair()
        try:
            a.send(struct.pack(">I", 10))     # claims 10 bytes, sends none
            with self.assertRaises(proto.ProtocolError):
                proto.recv_frame(b, timeout_ms=50)
        finally:
            a.close(); b.close()

    def test_peer_close_fail_closed(self):
        a, b = socket.socketpair()
        try:
            a.close()
            with self.assertRaises(proto.ProtocolError):
                proto.recv_frame(b, timeout_ms=100)
        finally:
            b.close()


class TestParsers(unittest.TestCase):
    def test_parse_hello_ok(self):
        session, hello = proto.parse_hello(hello_msg())
        self.assertEqual(session.session_id, SID)
        self.assertEqual(session.run_nonce, RN)
        self.assertEqual(session.manifest_sha256, MS)
        self.assertEqual(hello["input_kind"], "radioml-d2-2p56m")
        self.assertEqual(hello["sample_rate"], 2560000)
        self.assertEqual(hello["center_hz"], 2400000000)
        self.assertEqual(hello["target_rms"], 2048.0)

    def test_parse_hello_wrong_protocol(self):
        with self.assertRaises(proto.ProtocolError):
            proto.parse_hello(hello_msg(protocol=2))

    def test_parse_hello_unknown_field(self):
        with self.assertRaises(proto.ProtocolError):
            proto.parse_hello(hello_msg(bogus=1))

    def test_parse_hello_missing_field(self):
        m = hello_msg()
        del m["center_hz"]
        with self.assertRaises(proto.ProtocolError):
            proto.parse_hello(m)

    def test_parse_hello_nonpositive_target_rms(self):
        with self.assertRaises(proto.ProtocolError):
            proto.parse_hello(hello_msg(target_rms=0.0))

    def test_parse_hello_bad_manifest_sha(self):
        with self.assertRaises(proto.ProtocolError):
            proto.parse_hello(hello_msg(manifest_sha256="not-hex"))

    def test_parse_prepare_bad_session_id(self):
        session, _ = proto.parse_hello(hello_msg())
        with self.assertRaises(proto.ProtocolError):
            proto.parse_prepare(prepare_msg(session_id="other"), session)

    def test_parse_prepare_bad_nonce(self):
        session, _ = proto.parse_hello(hello_msg())
        with self.assertRaises(proto.ProtocolError):
            proto.parse_prepare(prepare_msg(run_nonce="other"), session)

    def test_parse_prepare_bad_manifest_sha(self):
        session, _ = proto.parse_hello(hello_msg())
        with self.assertRaises(proto.ProtocolError):
            proto.parse_prepare(prepare_msg(manifest_sha256="e" * 64), session)

    def test_parse_prepare_missing_source_index(self):
        session, _ = proto.parse_hello(hello_msg())
        m = prepare_msg()
        del m["source_index"]
        with self.assertRaises(proto.ProtocolError):
            proto.parse_prepare(m, session)

    def test_parse_prepare_bad_payload_sha(self):
        session, _ = proto.parse_hello(hello_msg())
        with self.assertRaises(proto.ProtocolError):
            proto.parse_prepare(prepare_msg(payload_sha_pre="short"), session)

    def test_parse_start_has_no_sha(self):
        # START/CAPTURED carry only source_index + file_name (no payload_sha_pre).
        session, _ = proto.parse_hello(hello_msg())
        sample = proto.parse_start(start_msg(), session)
        self.assertEqual(sample, {"source_index": 0, "file_name": "sample_000.ci16"})

    def test_parse_abort_ok(self):
        session, _ = proto.parse_hello(hello_msg())
        self.assertEqual(proto.parse_abort(abort_msg(), session),
                         {"reason": "board_done"})


class TestStateMachine(unittest.TestCase):
    def _new_session(self):
        engine = FakeEngine()
        a, b = socket.socketpair()
        sess = proto.PcTxServerSession(engine, a, message_timeout_ms=5000)
        return sess, engine, a, b

    def test_full_flow(self):
        sess, engine, a, b = self._new_session()
        try:
            sess._dispatch(hello_msg())
            ack = proto.recv_frame(b)
            self.assertEqual(ack["type"], "HELLO_ACK")
            self.assertTrue(ack["configuration_verified"])
            self.assertEqual(ack["tx_serial"], "1044734c9505000b")

            sess._dispatch(prepare_msg())
            prep = proto.recv_frame(b)
            self.assertEqual(prep["type"], "PREPARED")
            self.assertEqual(prep["payload_sha_post"], POST_SHA)
            self.assertEqual(prep["burst_sha"], BURST_SHA)
            self.assertNotIn("tx_running", prep)   # PREPARED never starts TX

            sess._dispatch(start_msg())
            ready = proto.recv_frame(b)
            self.assertEqual(ready["type"], "READY")
            self.assertTrue(ready["tx_running"])
            # READY carries the 11 payload fields (plan §7).
            for k in ("source_index", "file_name", "payload_sha_pre",
                      "payload_sha_post", "burst_sha", "tx_scale",
                      "sample_rate_readback", "tx_lo_readback", "tx_bw_readback",
                      "tx_atten_readback", "tx_running"):
                self.assertIn(k, ready)

            sess._dispatch(captured_msg())
            stopped = proto.recv_frame(b)
            self.assertEqual(stopped["type"], "STOPPED")
            self.assertTrue(stopped["tx_restore_ok"])

            self.assertEqual([e[0] for e in engine.events],
                             ["hello", "prepare", "start", "captured"])
        finally:
            a.close(); b.close()

    def test_start_without_prepare_rejected(self):
        sess, engine, a, b = self._new_session()
        try:
            sess._dispatch(hello_msg())
            proto.recv_frame(b)
            with self.assertRaises(proto.ProtocolError):
                sess._dispatch(start_msg())
        finally:
            a.close(); b.close()

    def test_duplicate_start_rejected(self):
        sess, engine, a, b = self._new_session()
        try:
            sess._dispatch(hello_msg())
            proto.recv_frame(b)
            sess._dispatch(prepare_msg())
            proto.recv_frame(b)
            sess._dispatch(start_msg())
            proto.recv_frame(b)
            with self.assertRaises(proto.ProtocolError):
                sess._dispatch(start_msg())   # already WAIT_CAPTURED
        finally:
            a.close(); b.close()

    def test_sample_identity_mismatch_rejected(self):
        sess, engine, a, b = self._new_session()
        try:
            sess._dispatch(hello_msg())
            proto.recv_frame(b)
            sess._dispatch(prepare_msg())              # source_index 0
            proto.recv_frame(b)
            with self.assertRaises(proto.ProtocolError):
                sess._dispatch(start_msg(source_index=1))
        finally:
            a.close(); b.close()

    def test_message_before_hello_rejected(self):
        sess, engine, a, b = self._new_session()
        try:
            with self.assertRaises(proto.ProtocolError):
                sess._dispatch(prepare_msg())
        finally:
            a.close(); b.close()

    def test_abort_after_hello(self):
        sess, engine, a, b = self._new_session()
        try:
            sess._dispatch(hello_msg())
            proto.recv_frame(b)
            ret = sess._dispatch(abort_msg())
            self.assertFalse(ret)                      # serve() should stop
            self.assertEqual(engine.events[-1][0], "abort")
        finally:
            a.close(); b.close()

    def test_emergency_stop_on_exception(self):
        # serve() must stop the TX on every exit path (finally).
        engine = FakeEngine()
        a, b = socket.socketpair()
        sess = proto.PcTxServerSession(engine, a, message_timeout_ms=100)
        try:
            a.send(struct.pack(">I", 10))   # truncated HELLO -> ProtocolError
            sess.serve()
        except proto.ProtocolError:
            pass
        finally:
            a.close(); b.close()
        self.assertIn("emergency_stop", [e[0] for e in engine.events])

    def test_serve_full_flow_over_socket(self):
        engine = FakeEngine()
        a, b = socket.socketpair()
        sess = proto.PcTxServerSession(engine, a, message_timeout_ms=5000)
        results = []

        def run_board():
            try:
                proto.send_frame(b, hello_msg())
                results.append(("ack", proto.recv_frame(b)["type"]))
                proto.send_frame(b, prepare_msg())
                results.append(("prepared", proto.recv_frame(b)["type"]))
                proto.send_frame(b, start_msg())
                ready = proto.recv_frame(b)
                results.append(("ready", ready["type"], ready["tx_running"]))
                proto.send_frame(b, captured_msg())
                stopped = proto.recv_frame(b)
                results.append(("stopped", stopped["type"], stopped["tx_restore_ok"]))
                proto.send_frame(b, abort_msg())
            except Exception as e:  # pragma: no cover - fail loudly
                results.append(("error", repr(e)))
            finally:
                b.close()

        t = threading.Thread(target=run_board)
        t.start()
        try:
            sess.serve()
        finally:
            a.close()
        t.join(timeout=5)
        self.assertEqual(results, [("ack", "HELLO_ACK"), ("prepared", "PREPARED"),
                                   ("ready", "READY", True),
                                   ("stopped", "STOPPED", True)])


class TestBuilders(unittest.TestCase):
    def test_build_hello_ack(self):
        session, _ = proto.parse_hello(hello_msg())
        m = proto.build_hello_ack(session, "ser", "usb:1.2.3", -40.0, True)
        self.assertEqual(m["type"], "HELLO_ACK")
        self.assertEqual(m["tx_serial"], "ser")
        self.assertEqual(m["tx_uri"], "usb:1.2.3")
        self.assertEqual(m["tx_atten_db"], -40.0)
        self.assertTrue(m["configuration_verified"])

    def test_build_prepared(self):
        session, _ = proto.parse_hello(hello_msg())
        m = proto.build_prepared(session, 0, "f.ci16", PRE_SHA, POST_SHA, BURST_SHA, 1.0)
        self.assertEqual(m["payload_sha_pre"], PRE_SHA)
        self.assertEqual(m["tx_scale"], 1.0)
        self.assertTrue(m["configuration_verified"])

    def test_build_ready_requires_all_readbacks(self):
        session, _ = proto.parse_hello(hello_msg())
        m = proto.build_ready(session, 0, "f.ci16", PRE_SHA, POST_SHA, BURST_SHA, 1.0,
                              2560000, 2400000000, 18000000, -40.0, True)
        self.assertTrue(m["tx_running"])
        self.assertEqual(m["sample_rate_readback"], 2560000)
        self.assertEqual(m["tx_atten_readback"], -40.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
