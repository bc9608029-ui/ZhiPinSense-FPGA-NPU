from pathlib import Path
import datetime,hashlib,json,os,subprocess,time,traceback
ROOT=Path('F:/FPGA_Work/smartscan_bram_fix1_20261030')
EVIDENCE=Path('F:/嵌赛/rml24_fpga_route_review_fix1_20261030/fix2')
OUT=ROOT/'outputs/smartscan_fix2_candidate'
STATUS=ROOT/'build/BITGEN_STATUS.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def status(**v):
 v.update(updated=datetime.datetime.now().astimezone().isoformat(),supervisor_pid=os.getpid())
 tmp=STATUS.with_suffix('.tmp');tmp.write_text(json.dumps(v,indent=2),encoding='utf-8');os.replace(tmp,STATUS)
def run(args,stage,env,marker=None):
 log=ROOT/'build'/('fix2_'+stage+'.stdout.log')
 with log.open('wb') as f:
  p=subprocess.Popen(subprocess.list2cmdline(args),shell=True,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
  while p.poll() is None:
   status(state='RUNNING',stage=stage,child_pid=p.pid,log=str(log));time.sleep(10)
 if p.returncode:raise RuntimeError(stage+' rc='+str(p.returncode))
 if marker and marker not in log.read_text(encoding='utf-8',errors='replace'):raise RuntimeError(stage+' completion marker missing')
def main():
 lock=ROOT/'build/bitgen.lock'
 fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
 try:
  env=dict(os.environ,TEMP=str(ROOT/'build/tmp'),TMP=str(ROOT/'build/tmp'),FMSH_PROCISE_PATH='D:/fudanwei/Procise',PYTHONIOENCODING='utf-8')
  for name in ['verify_change_scope.py','verify_baseline_exception.py']:
   run(['D:/Anaconda/python.exe',str(EVIDENCE/name)],name[:-3],env)
  dcp=ROOT/'reports_fix2/routed_fix2.dcp';dcp_sha=sha(dcp)
  run(['D:/Xilinx2018.3/Vivado/2018.3/bin/vivado.bat','-mode','batch','-source',str(ROOT/'fpga/generate_bit_candidate.tcl'),'-log',str(ROOT/'build/fix2_bitgen.log'),'-journal',str(ROOT/'build/fix2_bitgen.jou')],
      'bitgen',env,'FIX2_VENDOR_BITGEN_FINISHED_WITH_INHERITED_NPU_EXCEPTION')
  pe=dict(env,TCL_LIBRARY='D:/fudanwei/Procise/tcl8.4',ICTIME_HOME='D:/fudanwei/Procise',APP_DIR='D:/fudanwei/Procise',FMSH_DB='D:/fudanwei/Procise/db')
  pe['PATH']='D:/fudanwei/Procise/dll;D:/fudanwei/Procise/bin;'+pe.get('PATH','')
  run(['D:/fudanwei/Procise/bin/procise.exe',str(ROOT/'fpga/convert_candidate.tcl')],
      'explicit_conversion',pe,'FIX2_EXPLICIT_CONVERSION_FINISHED')
  raw=OUT/'smartscan_fix2_raw.bit';temp=OUT/'smartscan_fix2_disable_icap.bit.tmp'
  if raw.stat().st_size<1000000 or temp.stat().st_size<1000000:raise RuntimeError('short bitstream')
  auto=OUT/'smartscan_fix2_vendor_auto_disable_icap.bit'
  if not auto.exists():raise RuntimeError('vendor auto conversion output missing')
  if sha(auto)!=sha(temp):raise RuntimeError('AUTO_EXPLICIT_CONVERSION_MISMATCH')
  if sha(dcp)!=dcp_sha:raise RuntimeError('ROUTED_CHECKPOINT_CHANGED')
  final=OUT/'smartscan_fix2_disable_icap.bit'
  if final.exists():raise RuntimeError('FINAL_ALREADY_EXISTS')
  os.replace(temp,final)
  receipt={'state':'BITSTREAM_CANDIDATE_GENERATED_TARGET_ACCEPTANCE_PENDING',
    'time':datetime.datetime.now().astimezone().isoformat(),'routed_dcp_sha256':dcp_sha,
    'artifacts':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in [raw,auto,final]},
    'inherited_baseline_exception':json.loads((EVIDENCE/'BASELINE_EXCEPTION_GATE.json').read_text(encoding='utf-8')),
    'automatic_and_explicit_conversion_byte_identical':True,'full_sta_pass':False,
    'production_release':False,'board_tested':False,'fpga_programmed':False,'boot_changed':False}
  (OUT/'CANDIDATE_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
  status(state=receipt['state'],receipt=str(OUT/'CANDIDATE_RECEIPT.json'),production_release=False)
 except Exception as e:
  status(state='FAILED',error=str(e),traceback=traceback.format_exc(),production_release=False);raise
 finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()
