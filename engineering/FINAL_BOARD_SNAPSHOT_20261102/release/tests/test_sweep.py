import unittest
import sys
import math
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'candidate/rml24_final/runtime'))
from continuous_sweep import ContinuousSweep
from standalone_control import Controller,RestartAcquisition

class Lo:
    def __init__(self): self.current_hz=0;self.calls=[]
    def tune(self,hz):self.current_hz=hz;self.calls.append(hz);return hz
    def flush(self):pass

class SweepTests(unittest.TestCase):
    def probe(self,sweep,lo,values):
        it=iter(values)
        return sweep.probe([2400000000,2401000000],lo,lambda:lo.current_hz,
                           lambda z:SimpleNamespace(score=next(it),coarse_cfo_hz=0),
                           lambda:None,2399000000,2402000000)
    def test_never_locks(self):
        s=ContinuousSweep();lo=Lo()
        steps=[self.probe(s,lo,[.9,.9])[3] for _ in range(5)]
        self.assertEqual([x['scan_index'] for x in steps],[1,2,1,2,1])
        self.assertEqual([x['sweep_cycle'] for x in steps],[0,0,1,1,2])
    def test_silence_advances(self):
        s=ContinuousSweep();lo=Lo()
        self.assertIsNone(self.probe(s,lo,[0])[0]);self.assertEqual(s.index,1)
    def test_recenter_and_recapture(self):
        s=ContinuousSweep();lo=Lo();it=iter([100000,12])
        raw,center,_,step=s.probe([2400000000],lo,lambda:lo.current_hz,
            lambda z:SimpleNamespace(score=.9,coarse_cfo_hz=next(it)),lambda:None,2399000000,2402000000)
        self.assertEqual(lo.calls,[2400000000,2400100000]);self.assertEqual(raw,2400100000)
        self.assertEqual(center,2400100012);self.assertTrue(step['accepted'])
    def test_alias_and_nonfinite_rejected(self):
        for cfo in [2560000,-2560000,math.nan,math.inf]:
            s=ContinuousSweep();lo=Lo()
            raw,_,_,step=s.probe([2400000000],lo,lambda:0,
                lambda z:SimpleNamespace(score=.9,coarse_cfo_hz=cfo),lambda:None,2399000000,2402000000)
            self.assertIsNone(raw);self.assertFalse(step['accepted']);self.assertEqual(len(lo.calls),1)
    def test_false_recenter_rejected(self):
        s=ContinuousSweep();lo=Lo();it=iter([0,.9])
        raw,_,_,step=s.probe([2400000000],lo,lambda:0,
                lambda z:SimpleNamespace(score=next(it),coarse_cfo_hz=0),lambda:None,2399000000,2402000000)
        self.assertIsNone(raw)
    def test_failed_confirmation_advances(self):
        s=ContinuousSweep();lo=Lo();r=self.probe(s,lo,[.9,0])
        self.assertIsNone(r[0]);self.assertEqual(s.index,1)
    def test_stop_between_detection_and_confirm(self):
        s=ContinuousSweep();lo=Lo();calls=[]
        def checkpoint():
            calls.append(1)
            if len(calls)==2:raise RestartAcquisition()
        with self.assertRaises(RestartAcquisition):
            s.probe([2400000000],lo,lambda:0,lambda z:SimpleNamespace(score=.9,coarse_cfo_hz=0),checkpoint,2399000000,2402000000)
        self.assertEqual(len(lo.calls),1)
    def test_controller_accepts_three_modes(self):
        ctl=Controller(2400000000,2395000000,2405000000,1000000,2300000000,2500000000)
        lo=Lo()
        for mode in ['FIXED','BAND_SCAN','CONTINUOUS_SCAN']:
            c=ctl.submit('SET_MODE '+mode);self.assertTrue(ctl.drain(lo))
            self.assertTrue(c.done.is_set());self.assertEqual(ctl.snapshot()['mode'],mode)
        with self.assertRaises(ValueError):ctl.validate('SET_MODE AUTO_LOCK')
    def test_clear_resets_cursor(self):
        s=ContinuousSweep();lo=Lo();self.probe(s,lo,[0]);s.reset()
        self.assertEqual(self.probe(s,lo,[0])[3]['scan_index'],1)

if __name__=='__main__':unittest.main(verbosity=2)
