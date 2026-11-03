from pathlib import Path
import hashlib,json,re
HERE=Path(__file__).resolve().parent
BASE=Path('F:/FPGA_Work/sdr_full_chain_12class_combined_v1/outputs/smoke_v1')
NEW=Path('F:/FPGA_Work/smartscan_bram_fix1_20261030/reports_fix2')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def violations(p):
 rows=[]
 for line in p.read_text(encoding='utf-8',errors='replace').splitlines():
  a=line.split()
  if len(a)>=10 and a[:2]==['Min','Period']:
   try:slack=float(a[7])
   except ValueError:continue
   if slack<0:rows.append({'type':'Min Period','lib_pin':a[3],'required':float(a[5]),'actual':float(a[6]),'slack':slack,'pin':a[-1]})
 return sorted(rows,key=lambda x:x['pin'])
bit=BASE/'bitstream/combined_npu_hdmi_disable_icap.bit'
expected='22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9'
if sha(bit)!=expected:raise RuntimeError('WORKING_BASELINE_BIT_IDENTITY_MISMATCH')
oldr=BASE/'reports/timing_summary_routed.rpt';newr=NEW/'timing_summary.rpt'
old=violations(oldr);new=violations(newr)
if len(old)!=2 or old!=new:raise RuntimeError('INHERITED_MIN_PERIOD_SET_MISMATCH '+str((old,new)))
for p in [oldr,newr]:
 t=p.read_text(encoding='utf-8',errors='replace')
 if not re.search(r'clk_out1_AI_CORE_CLK_ST_1\s+\{0\.000 0\.500\}\s+1\.000\s+1000\.000',t):
  raise RuntimeError('CLOCK_IDENTITY_MISMATCH '+str(p))
review=json.loads((HERE/'FINAL_REPORT_REVIEW.json').read_text(encoding='utf-8'))
for key in ['routing_complete','setup_hold_clean','smartscan_no_cdc_critical_rows','default_drc_no_errors_or_critical_warnings','vendor_hook_did_not_change_timing_summary']:
 if not review['checks'][key]:raise RuntimeError('FAILED_GATE '+key)
scope=json.loads((HERE/'CHANGE_SCOPE.json').read_text(encoding='utf-8'))
if not all(x['unchanged'] for x in scope['frozen_netlists']+scope['constraints']):raise RuntimeError('FROZEN_IDENTITY_CHANGED')
result={'state':'INHERITED_BASELINE_EXCEPTION_MATCHES_CONTROLLED_CANDIDATE_GENERATION_ALLOWED',
 'baseline_bit_sha256':expected,'baseline_report_sha256':sha(oldr),'candidate_report_sha256':sha(newr),
 'violations':new,'full_sta_pass':False,'manufacturer_waiver_obtained':False,
 'board_loading_authorized_by_this_receipt':False,'production_release':False,
 'policy_evidence':'F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/docs/CDC_FALSE_PATH_EXCEPTION_AUDIT.md section 8'}
(HERE/'BASELINE_EXCEPTION_GATE.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
