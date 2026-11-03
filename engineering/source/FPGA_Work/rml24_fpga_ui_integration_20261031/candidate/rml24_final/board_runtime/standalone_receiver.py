#!/usr/bin/env python3
"""Autonomous public-frame receiver. No TCP or transmitter handshake."""
from __future__ import annotations
import argparse
import importlib
import json
import signal
import socket
import sys
import threading
import time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'runtime'))
sys.path.insert(0, str(ROOT/'recovery'))
sys.path.insert(0, str(Path(__file__).parent))
import candidate_two_dc
from receiver_core import recover_frame
from radio_tuning import RxLoController
from scan_runtime import ScanConfig, detect_public_training
from standalone_control import Controller, ControlServer, RestartAcquisition
from scan_lock_policy import LockHysteresis
from continuous_sweep import ContinuousSweep
from rml24_dualmode_receiver_centered_v2 import UiSocketClient, infer, write_json_atomic
from ui_event import build_ui_event, build_board_ui_result, set_spectrum_provider
from spectrum_backend import SpectrumBackend

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
    p.add_argument('--locked-misses-before-rescan',type=int,default=5)
    p.add_argument('--locked-rescan-hold-sec',type=float,default=1.0)
    p.add_argument('--initial-mode',choices=['FIXED','BAND_SCAN','CONTINUOUS_SCAN'],default='FIXED')
    p.add_argument('--duration-sec',type=float,default=0)
    p.add_argument('--save-captures',action='store_true')
    p.add_argument('--spectrum-backend',choices=['software','fpga','auto'],default='software')
    p.add_argument('--spectrum-driver')
    return p.parse_args()

def main():
    args=args_parse();out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    spectrum=SpectrumBackend(args.spectrum_backend,args.spectrum_driver,out/'spectrum_backend.jsonl')
    set_spectrum_provider(spectrum)
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
    lock_policy=LockHysteresis(args.locked_misses_before_rescan,
                               args.locked_rescan_hold_sec)
    sweep=ContinuousSweep()
    started=time.monotonic();last_state=0.0;locked=None;seq=0;valid=0;rejected=0;restore=[]
    def state(presence,force=False):
        nonlocal last_state
        ctl.update(presence=presence)
        now=time.monotonic()
        if not force and now-last_state<.5:return
        s=ctl.snapshot()
        ui.send(dict(type='state',version='rml24-standalone-state-v1',
                     command_id=s['command_id'],work_mode=s['mode'],
                     run_state='RUNNING' if s['running'] else 'STOPPED',
                     presence_state=presence,timestamp_us=time.time_ns()//1000,
                     model_sha='c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151'))
        last_state=now
    def checkpoint():
        nonlocal locked
        if stop.is_set() or (args.duration_sec and time.monotonic()-started>=args.duration_sec):
            stop.set();raise RestartAcquisition()
        if ctl.drain(lo):
            locked=None
            lock_policy.reset()
            sweep.reset()
            s=ctl.snapshot();state('ACQUIRING' if s['running'] else 'NO_SIGNAL',True)
            raise RestartAcquisition()
    try:
        radio.config_rx();lo=RxLoController(radio)
        actual=lo.tune(args.fixed_center_hz);lo.flush()
        ctl.update(actual_lo_hz=actual,fixed_readback_hz=actual)
        server=ControlServer(args.ui_control_socket,ctl);server.start()
        npu=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);npu.settimeout(20);npu.connect(args.npu_socket)
        print('STANDALONE_READY no_tcp=1 no_tx_handshake=1',flush=True)
        while not stop.is_set():
            try:
                checkpoint()
            except RestartAcquisition:
                continue
            s=ctl.snapshot()
            if not s['running']:
                state('NO_SIGNAL');stop.wait(.05);continue
            begin=time.monotonic();raw=None;steps=[];center=s['fixed_hz'];capture_ns=0
            try:
                if s['mode']=='FIXED':
                    if lo.current_hz!=s['fixed_hz']:
                        actual=lo.tune(s['fixed_hz']);lo.flush()
                        ctl.update(actual_lo_hz=actual,fixed_readback_hz=actual)
                    state('ACQUIRING')
                    raw=np.asarray(radio.receive(65536));capture_ns=time.time_ns()
                elif s['mode']=='CONTINUOUS_SCAN':
                    state('ACQUIRING')
                    config=ScanConfig(s['start_hz'],s['stop_hz'],s['step_hz'])
                    raw,center,capture_ns,step=sweep.probe(
                        config.lo_frequencies(),lo,
                        lambda:np.asarray(radio.receive(65536)),
                        lambda z:detect_public_training(z,public.train),checkpoint,
                        s['start_hz'],s['stop_hz'])
                    steps.append(step)
                    ctl.update(actual_lo_hz=lo.current_hz,scan_index=step['scan_index'],
                               scan_points=step['scan_points'],sweep_cycle=step['sweep_cycle'])
                else:
                    state('ACQUIRING')
                    if locked is not None:
                        candidate=np.asarray(radio.receive(65536));capture_ns=time.time_ns()
                        d=detect_public_training(candidate,public.train)
                        ok=d.score>=.10 and abs(d.coarse_cfo_hz)<=1000
                        steps.append(dict(lo_hz=lo.current_hz,public_score=d.score,
                                          cfo_hz=d.coarse_cfo_hz,locked_check=True,accepted=ok))
                        if ok:raw=candidate;center=int(round(lo.current_hz+d.coarse_cfo_hz))
                        else:
                            # A transient buffer boundary must not immediately
                            # launch the ~20 s full sweep.  Keep the last verified
                            # LO until the bounded, label-blind miss budget expires.
                            if lock_policy.miss(time.monotonic()):
                                locked=None
                                lock_policy.reset()
                    if raw is None and locked is None:
                        config=ScanConfig(s['start_hz'],s['stop_hz'],s['step_hz'])
                        frequencies=config.lo_frequencies();best=None
                        for index,hz in enumerate(frequencies):
                            checkpoint()
                            actual=lo.tune(hz);lo.flush()
                            ctl.update(actual_lo_hz=actual,scan_index=index+1,scan_points=len(frequencies))
                            state('ACQUIRING',True)
                            candidate=np.asarray(radio.receive(65536))
                            d=detect_public_training(candidate,public.train)
                            steps.append(dict(lo_hz=actual,public_score=d.score,cfo_hz=d.coarse_cfo_hz,
                                              locked_check=False,accepted=d.score>=.10))
                            if d.score>=.10 and (best is None or d.score>best[0]):
                                best=(d.score,actual+d.coarse_cfo_hz)
                        if best:
                            actual=lo.tune(int(round(best[1])));lo.flush()
                            ctl.update(actual_lo_hz=actual)
                            candidate=np.asarray(radio.receive(65536));capture_ns=time.time_ns()
                            d=detect_public_training(candidate,public.train)
                            if d.score>=.10 and abs(d.coarse_cfo_hz)<=1000:
                                raw=candidate;locked=actual;lock_policy.hit();center=int(round(actual+d.coarse_cfo_hz))
                arm={};tensor=None;frame=None
                if raw is not None:
                    try:
                        frame=recover_frame(raw,candidate_two_dc.recover)
                    except Exception as exc:
                        arm=dict(pred=-1,finite=False,error=type(exc).__name__+': '+str(exc))
                        if lock_policy.miss(time.monotonic()):
                            locked=None
                            lock_policy.reset()
                if frame is not None:
                    lock_policy.hit()
                    tensor=frame.tensor;arm.update(frame.metadata,input_sha256=frame.tensor_sha256)
                    # Failure of real NPU inference is fatal, not disguised as no signal.
                    arm.update(infer(npu,tensor));arm['finite']=True;valid+=1
                    measure_start=time.monotonic_ns()
                    z=(tensor[:,0,:]+1j*tensor[:,1,:]).mean(axis=0,dtype=np.complex128)
                    energy=float(np.sum(np.abs(z)**2))
                    ctl.update(frame_id=seq,rms_iq=float(np.sqrt(energy/1024)),
                               peak_iq=float(np.max(np.abs(z))),energy_iq2=energy,
                               feature_latency_us=(time.monotonic_ns()-measure_start)/1000,
                               backend='software')
                    event=build_ui_event(seq,arm,display_tensor=tensor)
                    ctl.update(backend=spectrum.last_backend)
                    result=build_board_ui_result(event,center_hz=center,
                             work_mode={'FIXED':'FIXED','BAND_SCAN':'BAND SCAN',
                                        'CONTINUOUS_SCAN':'CONTINUOUS SCAN'}[s['mode']])
                    if result is not None:ui.send(result)
                    state('SIGNAL_PRESENT',True)
                else:
                    arm.setdefault('pred',-1);arm.setdefault('finite',False)
                    arm.setdefault('error','NO_VALID_PUBLIC_FRAME');rejected+=1
                    state('NO_SIGNAL',True)
                elapsed=(time.monotonic()-begin)*1000
                row=dict(frame_id=seq,mode=s['mode'],capture_time_ns=capture_ns,
                         board_monotonic=time.monotonic(),center_hz=center,
                         actual_lo_hz=lo.current_hz,candidate=arm,scan_steps=steps,elapsed_ms=elapsed)
                if args.save_captures and raw is not None:
                    np.save(out/('%06d.raw.npy'%seq),raw)
                    if frame is not None:(out/('%06d.inputs.bin'%seq)).write_bytes(frame.tensor_bytes)
                with (out/'records.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
                write_json_atomic(out/'status.json',dict(valid=valid,rejected=rejected,records=seq+1,
                                  no_tcp=True,no_tx_handshake=True,tuning=ctl.snapshot()))
                print(json.dumps(dict(frame_id=seq,pred=arm['pred'],mode=s['mode'],center_hz=center)),flush=True)
                seq+=1
                if not arm['finite']:stop.wait(.15)
            except RestartAcquisition:
                continue
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
            write_json_atomic(out/'final.json',dict(valid=valid,rejected=rejected,records=seq,
                                      no_tcp=True,no_tx_handshake=True,restore_errors=restore,
                                      ui_sent=ui.sent,ui_failed=ui.failed))
    print('STANDALONE_COMPLETE records=%d valid=%d rejected=%d restore_errors=%d' % (seq,valid,rejected,len(restore)),flush=True)
    return 0 if not restore else 2

if __name__=='__main__':
    raise SystemExit(main())
