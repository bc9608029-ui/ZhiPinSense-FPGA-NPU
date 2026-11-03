"""Offline only: no IIO import/context, NPU inference or FPGA access."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import tempfile,unittest,numpy as np,json,subprocess
from unittest.mock import patch
from common import ROOT,load
from parameter_plan import create
from parameter_score import score,choose
same=load('same_iq_test',ROOT/'fpga/same_iq.py')

class Tests(unittest.TestCase):
 def fixture(self):
  p=dict(rows=[dict(opportunity=0,label=4,start_ns=0,end_ns=8_000_000_000)],margin_ns=500_000_000)
  cap=[dict(record_id=0,capture_start_ns=3_000_000_000,capture_end_ns=3_100_000_000,sha256='a'),
       dict(record_id=1,capture_start_ns=4_000_000_000,capture_end_ns=4_100_000_000,sha256='b')]
  r=[dict(record_id=i,raw_sha256='ab'[i],arms={str(n):dict(valid=True,pred=4 if i==0 else 5) for n in (1,2,4,8)}) for i in range(2)]
  ev=[dict(opportunity=0,start_ns=0,end_ns=8_000_000_000)];clock=dict(lo_ns=-1_000_000,hi_ns=1_000_000)
  return p,cap,r,ev,clock,clock
 def test_01_source_plan(self):self.assertEqual(len(create(ROOT/'tx/assets',1_000_000_000)['rows']),24)
 def test_02_no_correct_frame_selection(self):
  out=score(*self.fixture());self.assertEqual(out['rows'][0]['record_id'],1);self.assertEqual(out['correct']['8'],0)
 def test_03_missing_retains_denominator(self):
  args=list(self.fixture());args[1]=[];o=score(*args);self.assertEqual((o['denominator'],o['selected'],o['correct']['8']),(1,0,0))
 def test_04_invalid_prediction(self):
  args=list(self.fixture());args[2][1]['arms']['8']=dict(valid=False,pred=4)
  self.assertEqual(score(*args)['rows'][0]['pred']['8'],-1)
 def test_05_duplicate_capture(self):
  a=list(self.fixture());a[1].append(a[1][0])
  with self.assertRaises(ValueError):score(*a)
 def test_06_sha_mismatch(self):
  a=list(self.fixture());a[2][1]['raw_sha256']='x'
  with self.assertRaises(ValueError):score(*a)
 def test_07_no_inference_not_accuracy(self):
  a=list(self.fixture());a[2][1]['arms']['8']['pred']=None
  with self.assertRaises(ValueError):score(*a)
 def test_08_clock_uncertain(self):
  a=list(self.fixture());a[4]=dict(lo_ns=-300_000_000,hi_ns=0)
  with self.assertRaises(ValueError):score(*a)
 def test_09_boundary_capture_rejected(self):
  self.assertIsNone(choose([dict(record_id=1,capture_start_ns=0,capture_end_ns=10)],0,100,0,0,10))
 def test_10_fft_reference_identity(self):
  x=np.random.default_rng(5).integers(-1024,1025,(1024,2),dtype=np.int16)
  self.assertTrue(same.compare(x,same.gold.spectrum(x)['power_u54'].astype('<u8'))['pass_'])
 def test_11_fft_zero(self):self.assertTrue(same.compare(np.zeros((1024,2),np.int16),np.zeros(1024,np.uint64))['pass_'])
 def test_12_fft_high_bits_rejected(self):
  v=np.zeros(1024,np.uint64);v[0]=1<<54
  with self.assertRaises(ValueError):same.compare(np.zeros((1024,2),np.int16),v)
 def test_13_fft_mirror_rejected(self):
  z=512*np.exp(2j*np.pi*37*np.arange(1024)/1024);x=np.stack([z.real,z.imag],axis=1).round().astype(np.int16)
  v=same.gold.spectrum(x)['power_u54'].astype('<u8')
  self.assertFalse(same.compare(x,v[::-1])['pass_'])
 def test_14_repeat_n(self):
  mod=load('repeat_test',ROOT/'gain_tools/repeat_ablation.py');x=np.random.default_rng(4).normal(size=(8,2,1024)).astype('<f4')
  for n in (1,2,4,8):np.testing.assert_array_equal(mod.average_first(x,n)[0],x[:n].mean(axis=0,dtype=np.float64).astype('<f4'))
 def test_15_full_plan(self):self.assertEqual(len(create(ROOT/'tx/assets',1_000_000_000,count_per_class=10)['rows']),240)
 def fallback(self,code):
  with tempfile.TemporaryDirectory(dir=ROOT) as d:
   d=Path(d);np.zeros((1024,2),'<i2').tofile(d/'iq.i16')
   with patch.object(sys,'argv',['same_iq','--iq',str(d/'iq.i16'),'--out',str(d/'run'),
                                '--backend','auto','--driver',str(d/'unused')]),\
        patch.object(same.subprocess,'run',return_value=subprocess.CompletedProcess([],code,'','injected')):
    rc=same.main()
   return rc,json.loads((d/'run/result.json').read_text())
 def test_16_auto_idle_fault_fallback(self):
  rc,r=self.fallback(1);self.assertEqual(rc,0);self.assertEqual(r['backend_used'],'software');self.assertTrue(r['ok'])
 def test_17_busy_cannot_silently_continue(self):
  rc,r=self.fallback(3);self.assertEqual(rc,3);self.assertTrue(r['requires_board_reset']);self.assertFalse(r['ok'])
 def test_18_npu_wire_fragmentation(self):
  replay=load('replay_wire_test',ROOT/'gain_tools/replay_repeats.py')
  class Socket:
   def __init__(self):self.sent=0;self.pending=b''
   def sendall(self,data):
    assert len(data)==8192;self.sent+=1
    logits=np.zeros(24,'<f4');logits[4]=1;self.pending=logits.tobytes()
   def recv(self,n):out=self.pending[:min(n,17)];self.pending=self.pending[len(out):];return out
  sock=Socket();logits,pred=replay.infer(sock,np.zeros((8,2,1024),'<f4'))
  self.assertEqual((sock.sent,pred,logits.shape),(8,4,(8,24)))
 def test_19_clock_bracket(self):
  from parameter_score import verify_clock_bracket
  p=dict(start_ns=100,end_ns=200)
  before=dict(kind='BOARD_MINUS_PC_CLOCK_BOUND',samples=[dict(pc_before_ns=80,pc_after_ns=90)])
  after=dict(kind='BOARD_MINUS_PC_CLOCK_BOUND',samples=[dict(pc_before_ns=210,pc_after_ns=220)])
  verify_clock_bracket(p,before,after)
  with self.assertRaises(ValueError):verify_clock_bracket(p,after,after)
 def test_20_success_without_psd_is_not_fallback_success(self):
  rc,r=self.fallback(0);self.assertEqual(rc,1);self.assertFalse(r['ok'])

if __name__=='__main__':unittest.main(verbosity=2)
