"""Detached, single-worker offline build. Reports first; never touches board."""
from pathlib import Path
import datetime,json,os,subprocess,sys,time,traceback
ROOT=Path('F:/FPGA_Work/smartscan_bram_fix1_20261030')
STATUS=ROOT/'build/PIPELINE_STATUS.json'
def status(**v):
    v['updated']=datetime.datetime.now().astimezone().isoformat();v['supervisor_pid']=os.getpid()
    tmp=STATUS.with_suffix('.tmp');tmp.write_text(json.dumps(v,indent=2));os.replace(tmp,STATUS)
def main():
    lock=ROOT/'build/pipeline.lock'
    fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
    try:
        for script,stage in [('m3_synth_smartscan.tcl','synthesis'),('implement_fix1.tcl','implementation')]:
            log=ROOT/'build'/(stage+'.stdout.log')
            env=dict(os.environ,FMSH_PROCISE_PATH='D:/fudanwei/Procise',TEMP=str(ROOT/'build/tmp'),TMP=str(ROOT/'build/tmp'))
            Path(env['TEMP']).mkdir(exist_ok=True)
            cmd=['D:/Xilinx2018.3/Vivado/2018.3/bin/vivado.bat','-mode','batch','-source',str(ROOT/'fpga'/script),
                 '-log',str(ROOT/'build'/(stage+'.log')),'-journal',str(ROOT/'build'/(stage+'.jou'))]
            with log.open('wb') as f:
                child=subprocess.Popen(subprocess.list2cmdline(cmd),shell=True,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                while child.poll() is None:
                    status(state='RUNNING',stage=stage,child_pid=child.pid,log=str(log));time.sleep(10)
            if child.returncode:raise RuntimeError(stage+' failed rc='+str(child.returncode))
            text=log.read_text(errors='replace')
            marker='==M3S_SYNTH_OK==' if stage=='synthesis' else 'FIX1_ROUTED_REPORTS_READY_NO_BITSTREAM'
            if marker not in text:raise RuntimeError(stage+' missing completion marker')
        status(state='REPORTS_READY_REVIEW_REQUIRED',production_bitstream=False)
    except Exception as exc:
        status(state='FAILED',error=str(exc),traceback=traceback.format_exc(),production_bitstream=False)
        raise
    finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()
