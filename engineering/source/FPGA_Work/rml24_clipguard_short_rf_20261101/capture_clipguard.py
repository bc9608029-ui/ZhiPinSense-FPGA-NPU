from pathlib import Path
import sys,time,json,subprocess,shutil,numpy as np,math
root=Path('/root/rml24_clipguard_short_rf_20261101');root.mkdir(exist_ok=False);sys.path.insert(0,str(Path(__file__).parent));sys.path.insert(0,'/root/amr_rescue_20261025');import pluto_link_probe as link
from gain_freeze_radio import GainFreeze
radio=None;rows=[];restore=[];stopped=False

def receive(n):
 try:return np.asarray(radio.receive(n))
 finally:
  kept=[];seen=set()
  for ch,old in radio.enabled:
   key=getattr(ch,'value',ch)
   if key not in seen:seen.add(key);kept.append((ch,old))
  radio.enabled[:]=kept

def stats(raw):
 c=np.r_[raw.real,raw.imag];return dict(min=float(c.min()),max=float(c.max()),peak=float(abs(c).max()),rail_count=int(np.sum((c==-2048)|(c==2047))))

def healthy():
 try:
  pid=int(subprocess.check_output(['systemctl','show','rml24-integrated','-p','MainPID','--value']).strip());args=Path('/proc/%d/cmdline'%pid).read_bytes().decode().strip('\0').split('\0');run=Path(args[args.index('--run')+1]);children=json.loads((run/'children.json').read_text());alive=all(Path('/proc/%d/cmdline'%x['pid']).exists() for x in children if x['role'] in ('npu','ui','rx'));ready=alive and all(token in (run/(role+'.log')).read_text(errors='replace') for role,token in [('npu','NPU_STREAM_READY'),('ui','UI_FB_READY'),('rx','STANDALONE_READY')]);return dict(ready=ready,run=str(run))
 except Exception:return dict(ready=False)
try:
 assert shutil.disk_usage('/').free>int(1.2*1024**3);subprocess.run(['systemctl','stop','rml24-integrated'],check=True);stopped=True;assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists();uris=link.scan_usb();assert len(uris)==1;radio=link.Radio(uris[0]);radio.config_rx();radio.set(radio.rx,'rf_bandwidth',5000000);radio.set(radio.rlo,'frequency',2403600000)
 def read(key):return radio.get(radio.rx,key)
 def write(key,value):
  rc=link.writeattr(radio.rx,key.encode(),str(value).encode())
  if rc<0:raise RuntimeError('RX gain write rejected '+key)
 controller=GainFreeze(read,write,lambda:receive(16384));deadline=time.monotonic()+330
 while time.monotonic()<deadline and len(rows)<120:
  cycle=time.monotonic();assert shutil.disk_usage('/').free>int(1.05*1024**3);freeze=controller.prepare_capture();initial=receive(65536);initial_ns=time.monotonic_ns();initial_stats=stats(initial);initial_name='pair_%03d_initial.npy'%len(rows);np.save(root/initial_name,initial);final=initial;final_ns=initial_ns;final_stats=initial_stats;steps=[];gain=freeze['readback_gain_db'];bounds=read('hardwaregain_available').strip('[]').split();low=float(bounds[0])
  for attempt in range(3):
   if final_stats['peak']<.9*2048:break
   backoff=6 if final_stats['rail_count'] else max(1,math.ceil(20*math.log10(final_stats['peak']/(.8*2048))));requested=max(low,gain-backoff)
   if requested>=gain:break
   write('hardwaregain',requested);actual=float(read('hardwaregain').split()[0]);assert abs(actual-requested)<=1;final=receive(65536);final_ns=time.monotonic_ns();final_stats=stats(final);steps.append(dict(before_gain=gain,requested=requested,readback=actual,stats=final_stats));gain=actual
  final_name=initial_name if not steps else 'pair_%03d_final.npy'%len(rows)
  if steps:np.save(root/final_name,final)
  rows.append(dict(index=len(rows),initial_file=initial_name,final_file=final_name,initial_mono_ns=initial_ns,final_mono_ns=final_ns,initial_stats=initial_stats,final_stats=final_stats,initial_gain=freeze,final_gain_db=gain,backoff_steps=steps,headroom_resolved=final_stats['rail_count']==0));(root/'PROGRESS.json').write_text(json.dumps(rows));time.sleep(max(0,3-(time.monotonic()-cycle)))
finally:
 if radio is not None:restore=radio.close() or []
 guard_clear=not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists();health=dict(ready=False)
 if stopped and guard_clear:
  subprocess.run(['systemctl','start','rml24-integrated'],check=True)
  for _ in range(40):
   health=healthy()
   if health['ready']:break
   time.sleep(.5)
 (root/'RESULT.json').write_text(json.dumps(dict(rows=rows,restore_errors=restore,guard_clear_before_restore=guard_clear,restored_health=health)))
 print('CLIP_CAPTURE_FINISHED',len(rows),restore,health,flush=True)
