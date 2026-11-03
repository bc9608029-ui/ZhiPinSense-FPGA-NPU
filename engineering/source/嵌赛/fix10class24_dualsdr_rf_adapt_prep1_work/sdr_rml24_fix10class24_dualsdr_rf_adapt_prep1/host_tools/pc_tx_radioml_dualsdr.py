#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pc_tx_radioml_dualsdr.py — M29-RML24-REALRF-FINETUNE-PILOT1 PC-side TX SDR service.

Real dual-SDR topology for the finetune-pilot1 capture (identical to fix10prep2's
pc_tx_sdr_fix10.py): the Windows PC owns the TX ADALM-Pluto and periodically emits the
frozen training-frame burst over 50-ohm coax; the board owns the RX Pluto and captures
it.  The two ends exchange ONLY control messages + sample identity + SHA over TCP
(fix10_tx_protocol.py) -- never real-time IQ, never an RX device on this side.

This process is the SERVER peer of the board's CLIENT (board_package/
pilot1_capture_runner.hpp -> iqpctbrx::TcpControlClient).  It:

  * reuses the fix10prep2 pc_tx_sdr_fix10.py TX engine + protocol + WSL burst builder
    (build_burst_cli.sh) UNCHANGED -- the burst build / libiio monkeypatch / watchdog /
    device I/O are all manifest-agnostic, so the PC and board still derive byte-identical
    payload_sha_pre / payload_sha_post / burst_sha / tx_scale from the same frozen ci16;
  * swaps ONLY the manifest loader to the pilot1 per-session manifests
    (pilot1_tx_manifest.py): the 3-col board-public tx_manifest.tsv (identity SHA) + the
    5-col PC-private tx_payload_manifest.tsv keyed by capture sequence `seq` (the value
    the board sends as `source_index` over the wire), with file_name = <source_id>.i16
    and payload_sha_pre = tx_payload_sha256; the payload .i16 is already quantized at the
    fixed public scale S, so target_rms is 0 (no rescale: payload_sha_post ==
    payload_sha_pre == tx_payload_sha256, tx_scale == 1.0);
  * prewarms EVERY dataset_index in the manifest before listen (so PREPARE can only ever
    hit the cache -- never WSL/g++ inside the 2-second window), then serves one board
    connection through the strict per-sample HELLO->PREPARE->PREPARED->START->READY->
    CAPTURED->STOPPED state machine.

The board runner sets input_kind default "radioml-finetune-pilot1" and manifest_sha256 =
SHA-256 of tx_manifest.tsv; this process fail-closes if either differs.

Run (isolated mode, radioconda, PC that owns the TX SDR):
    D:\\radioconda\\python.exe -I host_tools\\pc_tx_radioml_dualsdr.py ^
        --listen 0.0.0.0:39010 --tx-uri "<PC_TX_URI>" ^
        --tx-payload-dir "<dir with tx_manifest.tsv + .i16 payloads>" ^
        --input-kind radioml-finetune-pilot1 --center 2400000000 ^
        --sample-rate 2560000 --tx-bw 18000000 --tx-atten -40 ^
        --rf-path direct-cable --rf-tx-target-rms 0

Self-test (no device / no RF where possible; libiio checks require radioconda):
    python -I host_tools\\pc_tx_radioml_dualsdr.py --self-test
"""

import argparse
import importlib.util
import os
import socket
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_here_module(name, filename):
    """Return a module bound to THIS package's host_tools by absolute path, so
    `python -I` isolated mode never silently binds a same-name module from CWD."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot locate %s next to pc_tx_radioml_dualsdr.py" % filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# The fix10prep2 server: importing it runs its libiio monkeypatch + `import iio` and
# binds fix10_tx_protocol / fix10_burst_cache / fix10_iio_attr, BurstBuilder, TxEngine,
# Watchdog, and the log helpers -- all of which pilot1 reuses verbatim.
pc_tx_sdr = _load_here_module("pc_tx_sdr_fix10", "pc_tx_sdr_fix10.py")
# The pure pilot1 manifest loader (stdlib only; unit-testable without radioconda).
pilot1_manifest = _load_here_module("pilot1_tx_manifest", "pilot1_tx_manifest.py")

proto = pc_tx_sdr.proto
log = pc_tx_sdr.log
log_err = pc_tx_sdr.log_err
TxEngineError = pc_tx_sdr.TxEngineError
TxEngine = pc_tx_sdr.TxEngine
BurstBuilder = pc_tx_sdr.BurstBuilder
Watchdog = pc_tx_sdr.Watchdog
DEFAULT_PORT = proto.DEFAULT_PORT
WATCHDOG_TIMEOUT_MS = proto.WATCHDOG_TIMEOUT_MS
DEFAULT_CENTER_HZ = 2400000000
DEFAULT_SAMPLE_RATE_HZ = 2560000
DEFAULT_TX_BW_HZ = 18000000
DEFAULT_TX_ATTEN_DB = -40.0
DEFAULT_TARGET_RMS = 0.0
DEFAULT_INPUT_KIND = "radioml-finetune-pilot1"


class Pilot1TxEngine(TxEngine):
    """pilot1 TX engine: identical to fix10prep2's TxEngine except it loads the 3-col
    pilot1 identity + 5-col payload manifests (pilot1_tx_manifest.py) instead of the
    24-column route_d2_rf_manifest.tsv.  `prepare_from_cache` / `on_prepare` / `on_start` /
    `on_captured` / device I/O are inherited verbatim -- the row interface they consume
    (file_name / complex_count / quantized_sha256) is the only contract."""

    def __init__(self, tx_uri, frozen_dir, input_kind, tx_bw_hz, tx_atten_db):
        super(Pilot1TxEngine, self).__init__(
            tx_uri, frozen_dir, input_kind, tx_bw_hz, tx_atten_db)
        # Review 39e5 Blocker 2: two manifests replace the old 9-col one.
        self._identity = None   # 3-col board-public identity manifest (set in on_hello)
        self._payload = None    # 5-col PC-private payload manifest (set in prewarm)

    def on_hello(self, session, hello):
        # Identity fail-closed: the PC's tx payload dir must byte-match the board's
        # manifest_sha256 (SHA-256 of the 3-col board-public tx_manifest.tsv).
        self._identity = pilot1_manifest.Pilot1IdentityManifest(self.frozen_dir)
        pc_manifest_sha = self._identity.sha256()
        if pc_manifest_sha != session.manifest_sha256:
            log_err("manifest_sha256 mismatch (pc=%s board=%s)"
                    % (pc_manifest_sha, session.manifest_sha256))
            raise TxEngineError("manifest_sha256 mismatch (tx payload dir differs from board)")
        if hello["input_kind"] != self.input_kind:
            log_err("input_kind mismatch (cli=%s hello=%s)"
                    % (self.input_kind, hello["input_kind"]))
            raise TxEngineError("input_kind mismatch")

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

    def prewarm(self, seq, target_rms):
        """Build + cache the burst for capture sequence `seq` ONCE, before listen.

        PREPARE then only ever reads the cache (prepare_from_cache), never WSL/g++.
        `seq` (0..239) is the value the board sends as `source_index` over the wire; it
        indexes the PC-private 5-col `tx_payload_manifest.tsv` (never sent to the board).
        """
        if self._payload is None:
            self._payload = pilot1_manifest.Pilot1PayloadManifest(self.frozen_dir)
        # TxEngine.prepare_from_cache() is intentionally inherited unchanged and
        # reads its manifest through the base-class `_manifest` slot.  Pilot1 uses
        # a different loader, so publish the already validated PC-private payload
        # manifest through that slot as well.  Without this alias PREPARE crashes
        # at seq=0 even though all 240 bursts were successfully prewarmed.
        self._manifest = self._payload
        row = self._payload.lookup(seq)
        if self._work_dir is None:
            self._work_dir = tempfile.mkdtemp(prefix="pilot1_burst_")
        ci16_path = os.path.join(self.frozen_dir, row["file_name"])
        burst_bytes, prov = self._builder.build(
            ci16_path, row["complex_count"], row["quantized_sha256"],
            target_rms, self._work_dir)
        log("PREWARM seq=%d source_id=%s file_name=%s payload_sha_post=%s burst_sha=%s "
            "tx_scale=%.17g"
            % (seq, row["source_id"], row["file_name"], prov["payload_sha_post"],
               prov["burst_sha"], prov["tx_scale"]))
        return burst_bytes, prov


def _validate_serve_args(args):
    """Return None if serve-mode args are valid, else an error message."""
    if not args.tx_uri:
        return "--tx-uri is required in serve mode"
    if not args.tx_payload_dir:
        return "--tx-payload-dir is required in serve mode (dir with tx_manifest.tsv + .i16)"
    if args.rf_path != "direct-cable":
        return ("--rf-path must be 'direct-cable' (50-ohm SMA coax, no antenna, "
                "no amplifier) to authorize real RF TX; got '%s'" % args.rf_path)
    if args.tx_atten > -40.0:
        return "--tx-atten %.3f exceeds the -40 dB safety ceiling; refusing" % args.tx_atten
    return None


def _parse_listen(spec):
    if ":" in spec:
        host, _, port = spec.rpartition(":")
        return host or "0.0.0.0", int(port)
    return "0.0.0.0", int(spec)


def run_self_test():
    checks = []

    def check(name, ok, detail=""):
        checks.append(ok)
        log("SELF-TEST %-40s %s%s"
            % (name, "PASS" if ok else "FAIL", (" -- " + detail) if detail else ""))

    # (a) libiio DLL provenance + version (radioconda only; guarded so the pure
    #     manifest/protocol/burst-tool checks still run elsewhere).
    iio = pc_tx_sdr.iio
    lib_name = getattr(getattr(iio, "_lib", None), "_name", "")
    check("libiio.dll resolved to radioconda",
          lib_name.lower() == pc_tx_sdr._RADIOCONDA_LIBIIO.lower(), lib_name)
    version = getattr(iio, "version", (0, 0, ""))
    check("libiio version is 0.26", version[0] == 0 and version[1] == 26,
          ".".join(str(x) for x in version))

    # (b) protocol module provenance + frozen constants.
    check("protocol module from host_tools",
          os.path.basename(os.path.dirname(getattr(proto, "__file__", ""))) == "host_tools",
          getattr(proto, "__file__", ""))
    check("protocol constants frozen",
          proto.PROTOCOL_VERSION == 1 and proto.DEFAULT_PORT == 39010 and
          proto.MAX_MESSAGE_BYTES == (1 << 20) and proto.WATCHDOG_TIMEOUT_MS <= 2000,
          "protocol=%d port=%d max=%d watchdog_ms=%d"
          % (proto.PROTOCOL_VERSION, proto.DEFAULT_PORT,
             proto.MAX_MESSAGE_BYTES, proto.WATCHDOG_TIMEOUT_MS))

    # (c) pilot1 manifest loader (pure stdlib, runs under `python -I`).
    check("pilot1_tx_manifest self-test",
          pilot1_manifest.run_self_test() == 0, "inlined")

    # (d) WSL burst tool compiles against the h5 frame headers (compile-once warm-up).
    builder = BurstBuilder()
    wsl_sh = pc_tx_sdr.windows_to_wsl(builder.tool_sh)
    try:
        proc = subprocess.run(["wsl.exe", "bash", wsl_sh, "--self-check"],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="ignore", timeout=180)
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        ok = proc.returncode == 0 and "kTotalBurstComplex=" in out
        check("WSL burst tool --self-check", ok, out or err or ("exit %d" % proc.returncode))
    except (OSError, subprocess.TimeoutExpired) as e:
        check("WSL burst tool --self-check", False, str(e))

    # (e) engine identity: Pilot1TxEngine builds a Pilot1Manifest, not the d2 one.
    eng = Pilot1TxEngine("usb:1.2.3", "C:\\tx_payload", DEFAULT_INPUT_KIND,
                         DEFAULT_TX_BW_HZ, DEFAULT_TX_ATTEN_DB)
    check("Pilot1TxEngine is a TxEngine", isinstance(eng, TxEngine))
    check("Pilot1TxEngine frozen_dir", eng.frozen_dir == "C:\\tx_payload", eng.frozen_dir)

    # Regression for the real seq=0 failure: pilot1 prewarm uses its private
    # payload loader, while inherited prepare_from_cache reads `_manifest`.
    # Exercise that exact prewarm -> PREPARE path without opening an SDR.
    class _FakePayload(object):
        def lookup(self, seq):
            if seq != 0:
                raise KeyError(seq)
            return {
                "source_id": "s1_c00_i00",
                "file_name": "s1_c00_i00.i16",
                "complex_count": 1,
                "quantized_sha256": "a" * 64,
            }

    class _FakeBuilder(object):
        def __init__(self):
            self.cache = pc_tx_sdr.burst_cache.BurstCache()

        def build(self, path, complex_count, expect_sha, target_rms, work_dir):
            prov = {
                "payload_sha_pre": expect_sha,
                "payload_sha_post": expect_sha,
                "burst_sha": "b" * 64,
                "tx_scale": 1.0,
                "burst_complex": 1,
            }
            result = (b"\0\0\0\0", prov)
            key = pc_tx_sdr.burst_cache.burst_cache_key(
                path, complex_count, expect_sha, target_rms)
            self.cache.put(key, result)
            return result

    try:
        eng._payload = _FakePayload()
        eng._builder = _FakeBuilder()
        eng._target_rms = 0.0
        eng.prewarm(0, 0.0)
        prepared = eng.on_prepare(None, {
            "source_index": 0,
            "file_name": "s1_c00_i00.i16",
            "payload_sha_pre": "a" * 64,
        })
        check("pilot1 prewarm -> PREPARE manifest alias",
              eng._manifest is eng._payload and
              prepared["payload_sha_post"] == "a" * 64 and
              prepared["tx_scale"] == 1.0)
    except Exception as e:
        check("pilot1 prewarm -> PREPARE manifest alias", False, str(e))

    all_ok = all(checks)
    log("SELF-TEST %s (%d/%d checks)" % ("PASS" if all_ok else "FAIL",
                                         sum(1 for c in checks if c), len(checks)))
    return 0 if all_ok else 1


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="pc_tx_radioml_dualsdr.py",
        description="M29-RML24-REALRF-FINETUNE-PILOT1 PC-side TX SDR service (TX-only).")
    p.add_argument("--listen", default="0.0.0.0:%d" % DEFAULT_PORT,
                   help="bind host:port (default 0.0.0.0:%d)" % DEFAULT_PORT)
    p.add_argument("--tx-uri", default="",
                   help="libiio URI of the PC's TX SDR (REQUIRED in serve mode)")
    p.add_argument("--tx-payload-dir", default="",
                   help="dir with tx_manifest.tsv + .i16 payloads (REQUIRED in serve mode)")
    p.add_argument("--input-kind", default=DEFAULT_INPUT_KIND)
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


def main(argv):
    args = parse_args(argv)

    if args.self_test:
        return run_self_test()

    err = _validate_serve_args(args)
    if err:
        log_err(err)
        return 1

    host, port = _parse_listen(args.listen)

    engine = Pilot1TxEngine(args.tx_uri, args.tx_payload_dir, args.input_kind,
                            tx_bw_hz=args.tx_bw, tx_atten_db=args.tx_atten)

    # Prewarm EVERY capture sequence in the PC-private payload manifest BEFORE listen, so
    # PREPARE can only ever hit the cache (never WSL/g++ inside the 2-second window).
    try:
        payload = pilot1_manifest.Pilot1PayloadManifest(args.tx_payload_dir)
        for seq in sorted(payload.rows):
            engine.prewarm(seq, args.rf_tx_target_rms)
    except (TxEngineError, pc_tx_sdr.ManifestError,
            pilot1_manifest.ManifestError) as e:
        log_err("prewarm failed: %s" % e)
        return 1

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
        server.listen(1)
    except OSError as e:
        log_err("cannot bind %s:%d: %s" % (host, port, e))
        server.close()
        return 1

    log("listening on %s:%d tx_uri=%s tx_payload_dir=%s input_kind=%s tx_bw=%d "
        "tx_atten=%.2f rf_path=direct-cable"
        % (host, port, args.tx_uri, args.tx_payload_dir, args.input_kind,
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
    primary_error = None
    cleanup_error = None
    try:
        session = proto.PcTxServerSession(engine, conn)
        session.serve()
    except proto.ProtocolError as e:
        primary_error = "protocol violation: %s" % e
        log_err(primary_error)
        rc = 1
    except (TxEngineError, pc_tx_sdr.ManifestError,
            pilot1_manifest.ManifestError) as e:
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
