import sys,tempfile,json,unittest,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from tx_core import defaults,validate,mhz_to_hz,prepare,spectrum,CLASSES
from tx_worker import run
TEST_TMP=Path(__file__).resolve().parent/'_tmp'
TEST_TMP.mkdir(exist_ok=True)
tempfile.tempdir=str(TEST_TMP)

class CoreTests(unittest.TestCase):
 def test_exact_frequency(self):self.assertEqual(mhz_to_hz('2400.000001'),2400000001)
 def test_sub_hz_rejected(self):
  with self.assertRaises(ValueError):mhz_to_hz('2400.0000001')
 def test_nonfinite_rejected(self):
  for text in ['NaN','Infinity','abc','0','7000']:
   with self.assertRaises(ValueError):mhz_to_hz(text)
 def test_invalid_settings(self):
  for k,v in [('gain_db',0),('gain_db',float('nan')),('hold_sec',0),('mode','multi'),('class_index',24)]:
   c=defaults();c[k]=v
   with self.assertRaises(ValueError):validate(c)
 def test_all24_assets(self):
  c=defaults();c['mode']='cycle';p=prepare(c)
  self.assertEqual([i['name'] for i in p],CLASSES)
  for item in p:
   self.assertEqual(item['frame'].dtype,np.complex64)
   self.assertEqual(len(item['frame']),16384)
   self.assertTrue(np.isfinite(item['frame']).all())
   self.assertLessEqual(max(abs(item['frame'].real).max(),abs(item['frame'].imag).max()),2047)
 def test_spectrum_is_real_preview(self):
  p=prepare(defaults());s=spectrum(p[0]['frame'])
  self.assertEqual(len(s),2048);self.assertAlmostEqual(float(s.max()),0)
 def test_bad_sha_fails(self):
  c=defaults();doc=json.loads(Path(c['manifest']).read_text());doc['records'][0]['source_sha256']='0'*64
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/'manifest.json';path.write_text(json.dumps(doc));c['manifest']=str(path)
   # Use the class associated with the tampered first record.
   c['class_index']=int(doc['records'][0]['file'].split('_')[0])
   with self.assertRaises(ValueError):prepare(c)

class FakeRadio:
 def __init__(self,uri,fail_send=False,fail_read=False,fail_restore=False):
  self.tx='tx';self.tlo='lo';self.attrs={('tx','hardwaregain'):'-60',('tx','sampling_frequency'):'2560000',('tx','rf_bandwidth'):'18000000',('lo','frequency'):'2400000000',('lo','powerdown'):'1'};self.saved=[];self.active=[];self.closed=False
  self.fail_send=fail_send;self.fail_read=fail_read;self.fail_restore=fail_restore
 def set(self,ch,key,value):self.saved.append((ch,key,self.attrs[ch,key]));self.attrs[ch,key]=str(value)
 def get(self,ch,key):return '1' if self.fail_read else self.attrs[ch,key]
 def send(self,z):
  if self.fail_send:raise RuntimeError('injected send error')
  b=object();self.active.append(b);return b
 def stop(self,b):self.active.remove(b)
 def close(self):
  self.active.clear();self.closed=True
  for ch,key,value in reversed(self.saved):self.attrs[ch,key]=value
  self.saved=[]
  return ['injected restore error'] if self.fail_restore else []

class WorkerTests(unittest.TestCase):
 def execute(self,c,radio=None,stop_delay=.2):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)
   def stop():time.sleep(stop_delay);(p/'stop.request').touch()
   thread=threading.Thread(target=stop);thread.start()
   rc=run(c,p,(lambda uri:radio) if radio else None);thread.join()
   return rc,json.loads((p/'result.json').read_text(encoding='utf8')),[json.loads(l) for l in (p/'events.jsonl').read_text(encoding='utf8').splitlines()]
 def test_preview_never_constructs_radio(self):
  c=defaults();rc,res,rows=self.execute(c)
  self.assertEqual(rc,0);self.assertFalse(res['real']);self.assertEqual(res['restore_status'],'NOT_APPLICABLE')
  self.assertFalse(any(r['event']=='transmitting' for r in rows))
 def test_stop_restores_fake(self):
  c=defaults();c['real']=True;r=FakeRadio('fake');rc,res,rows=self.execute(c,r)
  self.assertEqual(rc,0);self.assertTrue(r.closed);self.assertFalse(r.active);self.assertEqual(res['restore_status'],'READBACK_RESTORE_OK');self.assertTrue(all(x['ok'] for x in res['restore_readback']));self.assertEqual(r.attrs['lo','powerdown'],'1')
 def test_exception_restores_fake(self):
  c=defaults();c['real']=True;r=FakeRadio('fake',fail_send=True);rc,res,_=self.execute(c,r)
  self.assertEqual(rc,1);self.assertTrue(r.closed);self.assertIn('send',res['error'])
 def test_readback_blocks_send(self):
  c=defaults();c['real']=True;r=FakeRadio('fake',fail_read=True);rc,res,rows=self.execute(c,r)
  self.assertEqual(rc,1);self.assertTrue(r.closed);self.assertFalse(any(x['event']=='transmitting' for x in rows))
 def test_restore_error_not_success(self):
  c=defaults();c['real']=True;r=FakeRadio('fake',fail_restore=True);rc,res,_=self.execute(c,r)
  self.assertEqual(rc,1);self.assertEqual(res['restore_status'],'UNVERIFIED')
 def test_stop_before_start(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'stop.request').touch();c=defaults();c['real']=True;r=FakeRadio('fake')
   run(c,p,lambda uri:r)
   self.assertTrue(r.closed);self.assertEqual(r.saved,[])
if __name__=='__main__':unittest.main()
