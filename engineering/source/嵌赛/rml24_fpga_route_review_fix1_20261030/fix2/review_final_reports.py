from pathlib import Path
import re,json,hashlib,datetime
HERE=Path(__file__).resolve().parent
ROOT=Path('F:/FPGA_Work/smartscan_bram_fix1_20261030/reports_fix2')
def timing(p):
 text=p.read_text(encoding='utf-8',errors='replace')
 rows=[s.split() for s in text.splitlines() if re.fullmatch(r'\s*(?:[-+]?\d+(?:\.\d+)?\s+){11}[-+]?\d+(?:\.\d+)?\s*',s)]
 if not rows:raise RuntimeError('NO_TIMING_SUMMARY '+str(p))
 a=rows[0]
 return dict(zip(['WNS','TNS','setup_failing','setup_endpoints','WHS','THS','hold_failing','hold_endpoints','WPWS','TPWS','pulse_failing','pulse_endpoints'],[float(x) for x in a]))
before=timing(ROOT/'timing_before_vendor_post.rpt');after=timing(ROOT/'timing_summary.rpt')
route=(ROOT/'route_status.rpt').read_text(encoding='utf-8',errors='replace')
def route_n(label):
 m=re.search(r'# of '+label+r'\.+\s*:\s*(\d+)',route)
 if not m:raise RuntimeError('MISSING_ROUTE_METRIC '+label)
 return int(m.group(1))
rn={key:route_n(label) for key,label in [('routable','routable nets'),('fully_routed','fully routed nets'),('routing_errors','nets with routing errors')]}
cdc=(ROOT/'cdc.rpt').read_text(encoding='utf-8',errors='replace')
own=[s for s in cdc.splitlines() if re.match(r'\s*\d+\s+CDC-\d+\s+',s) and 'u_smart_scan/' in s]
drc=(ROOT/'drc.rpt').read_text(encoding='utf-8',errors='replace')
drc_bad=[s for s in drc.splitlines() if re.match(r'^\|',s) and re.search(r'\|\s*(Error|Critical Warning)\s*\|',s)]
checks={'routing_complete':rn['routable']==rn['fully_routed'] and rn['routing_errors']==0,
 'setup_hold_clean':all(after[k]>=0 for k in ['WNS','TNS','WHS','THS']) and after['setup_failing']==0 and after['hold_failing']==0,
 'pulse_min_period_clean':after['WPWS']>=0 and after['pulse_failing']==0,
 'vendor_hook_did_not_change_timing_summary':before==after,
 'smartscan_no_cdc_critical_rows':not any(re.search(r'\bCritical\b',s) for s in own),
 'default_drc_no_errors_or_critical_warnings':not drc_bad}
result={'time':datetime.datetime.now().isoformat(),'state':'ROUTED_SETUP_HOLD_PASS_CLOCK_MIN_PERIOD_REVIEW_PENDING',
 'checks':checks,'timing_before_vendor_post':before,'timing_after_vendor_post':after,'route':rn,
 'smartscan_cdc_rows':own,'drc_blocking_rows':drc_bad,'all_cdc_reviewed':False,
 'integrated_core_clock_mhz':50,'ooc_target_mhz':100,'bitstream_generated':False,'board_tested':False,
 'report_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*.rpt')}}
(HERE/'FINAL_REPORT_REVIEW.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ['state','checks','route','timing_after_vendor_post']},indent=2))
