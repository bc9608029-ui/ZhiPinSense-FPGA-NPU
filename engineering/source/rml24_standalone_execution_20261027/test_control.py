import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'candidate/rml24_final/runtime'))
from standalone_control import Controller

class Lo:
    current_hz=2400000000
    calls=None
    fail=False
    def __init__(self):self.calls=[]
    def tune(self,hz):
        self.calls.append(hz)
        if self.fail and hz==2401000000:
            raise RuntimeError('readback failed after hardware write')
        self.current_hz=hz
        return hz
    def flush(self):pass

class Tests(unittest.TestCase):
    def setUp(self):
        self.c=Controller(2400000000,2395000000,2405000000,1000000,2300000000,2500000000)
        self.c.update(actual_lo_hz=2400000000)
        self.lo=Lo()
    def test_ack_after_readback(self):
        q=self.c.submit('SET_FIXED_HZ 2401000000')
        self.assertFalse(q.done.is_set())
        self.assertEqual(self.c.snapshot()['fixed_hz'],2400000000)
        self.c.drain(self.lo)
        self.assertIn('applied_fixed_hz=2401000000',q.response)
    def test_rollback_after_failed_write(self):
        self.lo.fail=True
        q=self.c.submit('SET_FIXED_HZ 2401000000');self.c.drain(self.lo)
        self.assertIn('DEVICE_REJECTED',q.response)
        self.assertEqual(self.lo.calls,[2401000000,2400000000])
        self.assertEqual(self.c.snapshot()['fixed_hz'],2400000000)
    def test_invalid(self):
        for s in ['SET_FIXED_HZ -1','SET_FIXED_HZ 2.4e9','SET_FIXED_HZ 2500000001',
                  'SET_SCAN_RANGE_HZ 2400000000 2395000000 1000000',
                  'SET_SCAN_RANGE_HZ 2395000000 2405000000 0',
                  'SET_SCAN_RANGE_HZ 2395000000 2405000000 3000000',
                  'SET_SCAN_RANGE_HZ 2395000000 2405000000 1','SET_MODE AUTO_LOCK']:
            with self.subTest(s=s),self.assertRaises(ValueError):self.c.submit(s)
    def test_cancelled_not_applied(self):
        q=self.c.submit('SET_FIXED_HZ 2401000000');q.cancelled=True
        self.c.drain(self.lo);self.assertEqual(self.lo.calls,[])
    def test_scan_and_stop(self):
        for s in ['SET_MODE BAND_SCAN','STOP','START']:
            q=self.c.submit(s);self.c.drain(self.lo);self.assertTrue(q.done.is_set())
        self.assertEqual(self.c.snapshot()['mode'],'BAND_SCAN')
        q=self.c.submit('SET_FIXED_HZ 2401000000');self.c.drain(self.lo)
        self.assertIn('BUSY',q.response)

if __name__=='__main__':unittest.main(verbosity=2)
