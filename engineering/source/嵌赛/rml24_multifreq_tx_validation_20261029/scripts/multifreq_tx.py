#!/usr/bin/env python3
"""Parameterized multi-frequency transmit program (default dry-run: NO transmission).

The ONLY entry point for the frozen dual-path TX source.  Default is dry-run:
build the four scenarios (A-only / B-only / A+B / silence) from the frozen
contract, write the final int16 device waveforms + a report, and exit WITHOUT
touching any SDR.

Transmission happens only with ``--transmit`` AND an explicit ``--tx-uri`` that
is verified against the enumerated USB devices (never auto-picks).  TX config
(LO/Fs/BW/gain) is set then read back; any mismatch stops before transmit.
Every phase writes real events (prepared / start_requested / active / stop /
restore) with wall-clock + monotonic time and the waveform SHA.  Cleanup
destroys the TX buffer first, then restores attributes and reads them back item
by item; restore failures are recorded, never masked by exit code 0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

import tx_common as C

DEFAULT_PHASES = "silence,a_only,b_only,both,a_only,silence"
DEFAULT_PHASE_SECONDS = 10.0

# (Radio channel attr, iio attribute, value, readback absolute tolerance)
#   tx  -> radio.tx  (voltage0 output)
#   tlo -> radio.tlo (altvoltage1, the TX LO)
TX_CONFIG = [
    ("tx", "hardwaregain", C.TX_ATTEN_DB, 1.0),
    ("tx", "sampling_frequency", C.TX_SAMPLE_RATE, 1.0),
    ("tx", "rf_bandwidth", C.TX_BANDWIDTH_HZ, 1.0),
    ("tlo", "frequency", C.TX_LO_HZ, 1.0),
    ("tlo", "powerdown", 0, 0),
]
_CHANNEL = {"tx": "tx", "tlo": "tlo"}


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _first_float(s) -> float | None:
    m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(s))
    return float(m.group()) if m else None


def _wave_sha(w: np.ndarray) -> str:
    # same bytes as verify_tx_offline.py freezes (complex128 little-endian)
    return _sha_bytes(w.astype("<c16").tobytes())


def build_scenarios(args) -> dict[str, np.ndarray]:
    rows = C.load_manifest(Path(args.manifest))
    sel: dict[int, dict] = {}
    for cls in (args.class_a, args.class_b):
        row = next((v for v in rows if int(v["file"].split("_")[0]) == cls), None)
        if row is None:
            raise SystemExit(f"manifest has no class {cls}")
        sel[cls] = row
    dataset = Path(args.dataset)
    frames: dict[int, np.ndarray] = {}
    for cls, row in sel.items():
        data = (dataset / row["file"]).read_bytes()
        if _sha_bytes(data) != row["source_sha256"]:
            raise SystemExit(f"source SHA mismatch {row['file']}")
        frames[cls] = C.build_frame(data)
    dfA, dfB = C.SIGNAL_OFFSETS_HZ
    tx_a = C.resample_shift(frames[args.class_a], dfA)
    tx_b = C.resample_shift(frames[args.class_b], dfB)
    return {
        "a_only": tx_a,
        "b_only": tx_b,
        "both": tx_a + tx_b,
        "silence": np.zeros_like(tx_a),
    }


def verify_tx_uri(uris, tx_uri):
    """Fail-closed: the explicit TX URI must be among the enumerated devices."""
    if tx_uri not in uris:
        raise SystemExit(f"--tx-uri {tx_uri} not in enumerated {uris}")
    return True


def apply_config_and_readback(radio, config=TX_CONFIG):
    """Set each config item then read it back; return (readback, ok).

    ``ok`` is False if any readback is missing or deviates more than its
    tolerance -- the caller must stop before any transmission.
    """
    readback: dict[str, float | None] = {}
    ok = True
    for chname, attr, value, tol in config:
        ch = getattr(radio, _CHANNEL[chname])
        radio.set(ch, attr, value)
        rb = _first_float(radio.get(ch, attr))
        readback[f"{chname}.{attr}"] = rb
        if rb is None or abs(rb - float(value)) > tol:
            ok = False
    return readback, ok


def destroy_buffer_then_restore(radio, buffer):
    """Destroy the TX buffer FIRST, then restore attributes; return error list.

    Ordering matters: the cyclic DDS buffer must be torn down before the
    attributes (gain/LO) are restored.  Restore failures are returned, never
    masked by a clean exit code.
    """
    errors: list = []
    if buffer is not None:
        try:
            radio.stop(buffer)
        except Exception as exc:  # noqa: BLE001
            errors.append(("stop", repr(exc)))
        buffer = None
    try:
        errs = radio.close()
        if errs:
            errors.extend(errs)
    except Exception as exc:  # noqa: BLE001
        errors.append(("close", repr(exc)))
    return errors


def _dry_run(args, scenarios) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "kind": "OFFLINE_TX_DRY_RUN",
        "tx_center_hz": C.TX_LO_HZ,
        "sample_rate_hz": C.TX_SAMPLE_RATE,
        "signal_centers_hz": list(C.SIGNAL_CENTERS_HZ),
        "signal_offsets_hz": list(C.SIGNAL_OFFSETS_HZ),
        "class_a": args.class_a,
        "class_b": args.class_b,
        "phases": [{"name": n, "seconds": args.phase_seconds} for n in args.phases.split(",")],
        "config_would_apply": [{"channel": ch, "attr": attr, "value": value} for ch, attr, value, _ in TX_CONFIG],
        "scenarios": {},
    }
    for name, w in scenarios.items():
        iq = C.int16_quantize(w)
        dev_bytes = iq.tobytes()  # interleaved I/Q little-endian int16 (x16 rule)
        (out / f"device_{name}.i16").write_bytes(dev_bytes)
        comp = float(np.abs(iq).max())
        rms = float(np.sqrt(np.mean(np.abs(C.to_float(iq)) ** 2)))
        report["scenarios"][name] = {
            "wave_sha256": _wave_sha(w),
            "device_sha256": _sha_bytes(dev_bytes),
            "int16_peak": int(comp),
            "saturated_samples": C.saturation_count(w),
            "rms": rms,
            "n_samples": len(w),
        }
    (out / "dry_run_report.json").write_text(json.dumps(report, indent=2))
    print("DRY_RUN_OK " + json.dumps(report["scenarios"]))


def _transmit(args, scenarios) -> int:
    if not args.tx_uri:
        raise SystemExit("--transmit requires --tx-uri (never auto-pick a device)")
    if not args.link:
        raise SystemExit("--transmit requires --link (path to pluto_link_probe.py)")

    import importlib.util
    link_path = Path(args.link).resolve()
    spec = importlib.util.spec_from_file_location("_pluto_link_probe", str(link_path))
    link = importlib.util.module_from_spec(spec)
    sys.modules["_pluto_link_probe"] = link
    spec.loader.exec_module(link)

    uris = link.scan_usb()
    verify_tx_uri(uris, args.tx_uri)

    radio = link.Radio(args.tx_uri)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stop_file = Path(args.stop_file) if args.stop_file else None

    def _stop_requested() -> bool:
        return stop_file is not None and stop_file.exists()

    events: list[dict] = []

    def _ev(name: str, **kw) -> None:
        e = {"event": name, "wall_ns": time.time_ns(), "monotonic_ns": time.monotonic_ns()}
        e.update(kw)
        events.append(e)
        print("TX_EVENT " + json.dumps(e), flush=True)

    # capture originals BEFORE any change (for post-restore readback verification)
    originals: dict[str, str] = {}
    for chname, attr, _, _ in TX_CONFIG:
        ch = getattr(radio, _CHANNEL[chname])
        originals[f"{chname}.{attr}"] = radio.get(ch, attr)

    phases = [(n.strip(), args.phase_seconds) for n in args.phases.split(",") if n.strip()]
    buffer = None
    interrupted = False
    config_ok = True
    readback: dict[str, float | None] = {}

    try:
        readback, config_ok = apply_config_and_readback(radio)
        _ev("prepared", uri=args.tx_uri, config_readback=readback, config_ok=config_ok)
        if not config_ok:
            raise SystemExit("CONFIG_READBACK_MISMATCH " + json.dumps(readback))

        for name, dur in phases:
            if _stop_requested() or interrupted:
                _ev("skipped", phase=name,
                    reason="stop_file" if _stop_requested() else "interrupted")
                break
            w = scenarios[name]
            _ev("start_requested", phase=name, duration_s=dur, wave_sha256=_wave_sha(w))
            buffer = radio.send(w)
            _ev("active", phase=name)
            slept = 0.0
            try:
                while slept < dur and not _stop_requested():
                    step = min(0.5, dur - slept)
                    time.sleep(step)
                    slept += step
            except KeyboardInterrupt:
                interrupted = True
                _ev("interrupted", phase=name)
            if buffer is not None:
                radio.stop(buffer)
                buffer = None
            _ev("stop", phase=name, slept_s=round(slept, 3))
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - record, then still restore
        _ev("error", detail=repr(exc))
    finally:
        _ev("restore_begin")
        restore_errors = destroy_buffer_then_restore(radio, buffer)
        buffer = None
        _ev("restore", errors=restore_errors)

    # post-restore readback (fresh get-only context), compare to originals
    restore_readback: dict[str, str] = {}
    try:
        r2 = link.Radio(args.tx_uri)
        for chname, attr, _, _ in TX_CONFIG:
            ch = getattr(r2, _CHANNEL[chname])
            restore_readback[f"{chname}.{attr}"] = r2.get(ch, attr)
        r2.close()
    except Exception as exc:  # noqa: BLE001
        restore_readback = {"error": repr(exc)}

    restore_ok: dict[str, bool] = {}
    for key, orig in originals.items():
        got = restore_readback.get(key)
        a, b = _first_float(got), _first_float(orig)
        restore_ok[key] = (a is not None and b is not None and abs(a - b) <= 1e-6)

    report = {
        "kind": "OFFLINE_TX_TRANSMIT_RUN",
        "uri": args.tx_uri,
        "config_ok": config_ok,
        "config_readback": readback,
        "originals": originals,
        "restore_readback": restore_readback,
        "restore_ok": restore_ok,
        "restore_errors": restore_errors,
        "interrupted": interrupted,
        "events": events,
    }
    (out / "transmit_run.json").write_text(json.dumps(report, indent=2))
    restore_all_ok = all(restore_ok.values()) and not restore_errors and config_ok
    print("TX_DONE restore_ok=" + json.dumps(restore_ok) + " restore_errors=" + json.dumps(restore_errors))
    return 0 if restore_all_ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--class-a", type=int, default=3)
    ap.add_argument("--class-b", type=int, default=9)
    ap.add_argument("--phases", default=DEFAULT_PHASES)
    ap.add_argument("--phase-seconds", type=float, default=DEFAULT_PHASE_SECONDS)
    ap.add_argument("--dry-run", action="store_true", default=True, help="build+write, no TX (default)")
    ap.add_argument("--transmit", action="store_true", help="actually transmit (requires --tx-uri + --link)")
    ap.add_argument("--tx-uri", help="explicit TX Pluto URI, e.g. usb:1.12.5")
    ap.add_argument("--link", help="path to pluto_link_probe.py")
    ap.add_argument("--stop-file", help="optional path; its existence stops the phase loop early")
    args = ap.parse_args()

    scenarios = build_scenarios(args)

    if args.transmit:
        return _transmit(args, scenarios)
    # default (and explicit --dry-run): build + write, no SDR
    _dry_run(args, scenarios)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
