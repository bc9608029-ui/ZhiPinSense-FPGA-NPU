"""Run the real entry/wrapper with injected radio and NPU; no RF or model inference."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BOARD=ROOT/'candidate/rml24_final/board_runtime'
sys.path.insert(0,str(BOARD))
sys.path.insert(0,str(ROOT/'candidate/rml24_final/runtime'))
sys.path.insert(0,str(ROOT/'candidate/rml24_final/recovery'))
import standalone_receiver as rx
from receiver_core import tensorize,RecoveredFrame
import receiver_repeat_mean_gapfix1 as wrapper

class Radio:
    last=None
    def __init__(self,uri):self.hz=0;self.closed=False;self.calls=[];Radio.last=self
    def config_rx(self):pass
    def receive(self,n):return np.full(65536,1+1j,dtype=np.complex64)
    def close(self):self.closed=True;return []
class Lo:
    def __init__(self,r):self.r=r;self.current_hz=0
    def tune(self,hz):self.current_hz=hz;self.r.calls.append(hz);return hz
    def flush(self):pass
    def restore(self):pass
class UI:
    last=None
    def __init__(self,path):self.events=[];self.sent=0;self.failed=0;UI.last=self
    def send(self,event):self.events.append(event);self.sent+=1
    def close(self):pass
class Server:
    def __init__(self,*a):pass
    def start(self):pass
    def close(self):pass
class Socket:
    def settimeout(self,*a):pass
    def connect(self,*a):pass
    def close(self):pass

class Integration(unittest.TestCase):
    def run_mode(self,mode,fail=False):
        with tempfile.TemporaryDirectory(dir=ROOT/'evidence') as tmp:
            out=Path(tmp)/'run'
            args=types.SimpleNamespace(legacy_root=tmp,npu_socket='fake',out=str(out),ui_socket='fake',
                ui_control_socket='fake',fixed_center_hz=2400000000,scan_start_hz=2400000000,
                scan_stop_hz=2401000000,scan_step_hz=1000000,minimum_hz=2300000000,
                maximum_hz=2500000000,max_scan_points=101,locked_misses_before_rescan=5,
                locked_rescan_hold_sec=1,initial_mode=mode,duration_sec=0,save_captures=True)
            link=types.SimpleNamespace(scan_usb=lambda:['FAKE'],Radio=Radio)
            public=types.SimpleNamespace(train=np.ones(1024),tail=np.ones(1024))
            recover_calls=[]
            def recover(raw,func):
                recover_calls.append(1)
                if fail:raise ValueError('synthetic recovery failure')
                z=np.arange(8*1024).reshape(8,1024).astype(float)/1000+1j
                t,b,s=tensorize(z);return RecoveredFrame(t,b,s,{})
            def infer(sock,t):
                if len(recover_calls)>=4:raise RuntimeError('INJECTED_STOP')
                return dict(pred=4,mean_logits=[0.,0.,0.,0.,6.]+[0.]*19)
            count=[0]
            def detect(raw,train):
                count[0]+=1
                if fail and count[0]>8:raise RuntimeError('INJECTED_STOP')
                return types.SimpleNamespace(score=.9,coarse_cfo_hz=0)
            with contextlib.ExitStack() as stack:
                for name,value in dict(args_parse=lambda:args,RxLoController=Lo,UiSocketClient=UI,
                    ControlServer=Server,recover_frame=recover,infer=infer,detect_public_training=detect).items():
                    stack.enter_context(patch.object(rx,name,value))
                stack.enter_context(patch.object(rx.importlib,'import_module',lambda n:link if n=='pluto_link_probe' else public))
                stack.enter_context(patch.object(rx.socket,'socket',lambda *a:Socket()))
                stack.enter_context(patch.object(rx.socket,'AF_UNIX',1,create=True))
                stack.enter_context(patch.object(rx.signal,'signal',lambda *a:None))
                with contextlib.redirect_stdout(io.StringIO()),self.assertRaisesRegex(RuntimeError,'INJECTED_STOP'):
                    rx.main()
            self.assertTrue(Radio.last.closed)
            rows=[json.loads(x) for x in (out/'records.jsonl').read_text().splitlines()]
            events=UI.last.events
            return rows,events,Radio.last.calls
    def test_sweep_full_entry(self):
        rows,events,calls=self.run_mode('CONTINUOUS_SCAN')
        self.assertEqual([r['scan_steps'][0]['scan_index'] for r in rows],[1,2,1])
        self.assertEqual([r['center_hz'] for r in rows],[2400000000,2401000000,2400000000])
        self.assertEqual(len([e for e in events if e['type']=='result']),3)
        self.assertTrue(all(e['work_mode']=='CONTINUOUS SCAN' for e in events if e['type']=='result'))
    def test_fixed_full_entry(self):
        rows,events,calls=self.run_mode('FIXED')
        self.assertEqual(len(rows),3);self.assertTrue(all(not r['scan_steps'] for r in rows))
    def test_lock_still_holds(self):
        rows,events,calls=self.run_mode('BAND_SCAN')
        self.assertTrue(rows[0]['scan_steps']);self.assertTrue(rows[1]['scan_steps'][0]['locked_check'])
    def test_recovery_failure_continues(self):
        rows,events,calls=self.run_mode('CONTINUOUS_SCAN',True)
        self.assertEqual([r['scan_steps'][0]['scan_index'] for r in rows],[1,2,1,2])
        self.assertTrue(all(not r['candidate']['finite'] for r in rows))
    def test_frozen_repeat_mean_kept(self):
        wrapper.verify_base()
        z=np.random.default_rng(8).normal(size=(8,2,1024)).astype('<f4')
        from repeat_mean_candidate import preprocess
        output=preprocess(z)
        np.testing.assert_array_equal(output[0],output[7])
        np.testing.assert_allclose(output[0],z.mean(axis=0,dtype=np.float64).astype('<f4'),rtol=0,atol=0)

if __name__=='__main__':unittest.main(verbosity=2)
