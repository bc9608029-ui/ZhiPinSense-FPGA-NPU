#!/usr/bin/env python3
"""Autonomous public-frame receiver. No TCP or transmitter handshake.

C-LINE REFERENCE FILE (main thread merges at a single point; NOT applied to the
A/B trees in place).  This is the A-line ``standalone_receiver.py`` with its
hand-written scan/recover/classify loop REPLACED by the injectable
``multisignal_receiver_entry.ReceiverEntry`` (the C3 scheduler + C5 injectable
entry).  Every hardware/UI/NPU dependency is wired in the constructor; the loop
itself is shared with the offline integration tests, so what the board runs is
exactly what the tests exercised.

Honest deltas vs the A-line loop (main thread reconciliation points):
  * lock_policy hysteresis / locked-rescan-hold are delegated to the scheduler's
    fair revisit + periodic full-band rescan; the LockHysteresis object is no
    longer driven here.
  * per-dwell ``state('ACQUIRING')`` and the RMS/peak/energy feature
    measurements are not re-implemented by ReceiverEntry (its state event carries
    presence only); the main thread may re-add them around ``entry.step()``.
  * raw capture save (``--save-captures``) and the records/status/final.json
    schema are simplified (ReceiverEntry writes a compact records.jsonl);
    reconcile to the A-line schema if byte-compatibility is required.
"""
from __future__ import annotations
import argparse
import importlib
import signal
import socket
import sys
import threading
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'runtime'))
sys.path.insert(0, str(ROOT/'recovery'))
sys.path.insert(0, str(Path(__file__).parent))
import candidate_two_dc
from receiver_core import CLASS_NAMES, recover_frame
from radio_tuning import RxLoController
from scan_runtime import detect_public_training
from standalone_control import Controller, ControlServer
from rml24_dualmode_receiver_centered_v2 import UiSocketClient, infer, write_json_atomic
from ui_event import build_ui_event, build_board_ui_result
# C-LINE INSERTION POINT 0: the injectable multi-signal entry (C3 scheduler +
# C5 injectable loop).  Deploy integration/receiver_entry.py as
# multisignal_receiver_entry.py and src/scan_adapter.py as
# multisignal_scan_adapter.py next to this file (see integration/README.md).
from multisignal_receiver_entry import EntryConfig, ReceiverEntry, ScanLoopOptions


def args_parse():
    p=argparse.ArgumentParser()
    p.add_argument('--legacy-root',required=True)
    p.add_argument('--npu-socket',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--ui-socket',default='/run/rml24_standalone_ui.sock')
    p.add_argument('--ui-control-socket',default='/run/rml24_standalone_control.sock')
    p.add_argument('--fixed-center-hz',type=int,default=2400000000)
    p.add_argument('--scan-start-hz',type=int,default=2395000000)
    p.add_argument('--scan-stop-hz',type=int,default=2405000000)
    p.add_argument('--scan-step-hz',type=int,default=1000000)
    p.add_argument('--minimum-hz',type=int,default=2300000000)
    p.add_argument('--maximum-hz',type=int,default=2500000000)
    p.add_argument('--max-scan-points',type=int,default=101)
    p.add_argument('--initial-mode',choices=['FIXED','BAND_SCAN'],default='FIXED')
    p.add_argument('--duration-sec',type=float,default=0)
    p.add_argument('--save-captures',action='store_true')
    return p.parse_args()


class EntryRadio:
    """Adapter: ReceiverEntry expects ONE object with tune/flush/receive/close.
    The A-line splits these across ``lo`` (tune/flush) and ``radio`` (receive)."""
    def __init__(self, lo, radio):
        self.lo=lo;self.radio=radio
    def tune(self,hz):return self.lo.tune(hz)
    def flush(self):return self.lo.flush()
    def receive(self):return np.asarray(self.radio.receive(65536))
    def close(self):return self.radio.close()


def main():
    args=args_parse();out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(Path(args.legacy_root).resolve()))
    link=importlib.import_module('pluto_link_probe')
    public=importlib.import_module('pilot_recovery')
    ctl=Controller(args.fixed_center_hz,args.scan_start_hz,args.scan_stop_hz,
                   args.scan_step_hz,args.minimum_hz,args.maximum_hz,args.max_scan_points)
    ctl.update(mode=args.initial_mode)
    stop=threading.Event()
    for sig in [signal.SIGINT,signal.SIGTERM]:signal.signal(sig,lambda *_:stop.set())
    uris=link.scan_usb()
    if len(uris)!=1:raise RuntimeError('Expected exactly one RX Pluto: '+repr(uris))
    radio=link.Radio(uris[0]);lo=None;npu=None;server=None
    ui=UiSocketClient(args.ui_socket or None)
    entry=None
    restore=[]
    try:
        radio.config_rx();lo=RxLoController(radio)
        actual=lo.tune(args.fixed_center_hz);lo.flush()
        ctl.update(actual_lo_hz=actual,fixed_readback_hz=actual)
        server=ControlServer(args.ui_control_socket,ctl);server.start()
        npu=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);npu.settimeout(20);npu.connect(args.npu_socket)
        print('STANDALONE_READY no_tcp=1 no_tx_handshake=1',flush=True)

        # C-LINE INSERTION POINT 1: construct the injectable entry.  This is the
        # FINAL patched loop -- identical to what tests/test_entry_integration.py
        # drives offline (label-blind infer stub there, real NPU here).
        entry=ReceiverEntry(
            radio=EntryRadio(lo,radio),
            infer=lambda tensor: infer(npu,tensor),
            transport=ui,
            config=EntryConfig(
                fixed_center_hz=args.fixed_center_hz,
                scan_start_hz=args.scan_start_hz,scan_stop_hz=args.scan_stop_hz,
                scan_step_hz=args.scan_step_hz,initial_mode=args.initial_mode,
                duration_sec=args.duration_sec,out_dir=out,
                scheduler=ScanLoopOptions()),
            detector=lambda raw: detect_public_training(raw,public.train),
            recover=recover_frame,recover_fn=candidate_two_dc.recover,
            class_names=list(CLASS_NAMES),
            ui_event_builder=build_ui_event,ui_result_builder=build_board_ui_result,
            controller=ctl,
        )
        entry.stop=stop
        # C-LINE INSERTION POINT 2: run the shared loop until signal/duration.
        entry.run()
    finally:
        if server:server.close()
        if npu:npu.close()
        ui.close()
        if lo:
            try:lo.restore()
            except Exception as exc:restore.append('lo_restore:'+str(exc))
        try:
            errors=radio.close()
            if errors:restore.extend(map(str,errors))
        finally:
            write_json_atomic(out/'restore.json',restore)
            write_json_atomic(out/'final.json',dict(valid=entry.valid if entry else 0,
                                      rejected=entry.rejected if entry else 0,
                                      records=entry.seq if entry else 0,
                                      no_tcp=True,no_tx_handshake=True,restore_errors=restore,
                                      ui_sent=ui.sent,ui_failed=ui.failed))
    print('STANDALONE_COMPLETE records=%d valid=%d rejected=%d restore_errors=%d' % (
        entry.seq if entry else 0,
        entry.valid if entry else 0,
        entry.rejected if entry else 0,len(restore)),flush=True)
    return 0 if not restore else 2

if __name__=='__main__':
    raise SystemExit(main())
