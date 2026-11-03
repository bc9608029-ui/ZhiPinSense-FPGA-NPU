from pathlib import Path
import http.client,json,sys,time
sys.path.insert(0,'E:/FPGA_Work/rml24_timing_fix_20261031');from timing_contract import pc_monotonic_ns

def request(token,route,method='GET',body=None):
 conn=http.client.HTTPConnection('192.168.126.49',8766,timeout=10,source_address=('192.168.126.10',0))
 try:
  conn.request(method,'/'+token+'/'+route,body=body);response=conn.getresponse();data=response.read()
  if response.status!=200:raise RuntimeError('board API status '+str(response.status))
  return data
 finally:conn.close()
def clock(token):
 samples=[]
 for _ in range(5):
  begin=pc_monotonic_ns();value=json.loads(request(token,'clock'));end=pc_monotonic_ns();assert value['clock_id']=='board-monotonic-v1';samples.append(dict(offset_ns=(begin+end)//2-value['board_mono_ns'],uncertainty_ns=(end-begin)//2,board_boot_id=value['board_boot_id']))
 best=min(samples,key=lambda x:x['uncertainty_ns']);return dict(best,clock_id='windows-qpc-board-monotonic-v1',samples=samples)
