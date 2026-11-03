from pathlib import Path
import json,time,subprocess,sys,re,gzip,base64
p=Path(__file__).parent;old=Path('E:/FPGA_Work/rml24_locked_detection_research_20261101')
def ps(args):
 q=subprocess.run(['powershell','-NoProfile','-File']+args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);s=q.stdout.decode('utf8',errors='replace');assert q.returncode==0,s;return s
def board(cmd,seconds=3):return ps(['E:/scan_exec_20261027/serial.ps1','-Command',cmd,'-Seconds',str(seconds)])
for _ in range(180):
 if (p/'RESULT.json').exists() and (p/'CLOCK_POST.json').exists():break
 time.sleep(2)
else:raise RuntimeError('precision capture not complete')
sys.path.insert(0,'E:/FPGA_Work/rml24_gainfreeze_formal_prep_20261101');from timing_contract import validate_calibration
pre=json.loads((p/'CLOCK_PRE.json').read_text());post=json.loads((p/'CLOCK_POST.json').read_text());drift=validate_calibration(pre,post);ev=json.loads((p/'PRIVATE_EVENTS.json').read_text());v=json.loads((p/'RESULT.json').read_text());groups=[]
for e in ev:
 rs=[r for r in v['rows'] if e['start_mono_ns']+1500000000<=r['capture_monotonic_ns']+pre['offset_ns']<=e['end_mono_ns']-300000000];groups.append(dict(file=e['file'],event=e,rows=rs))
(p/'GROUPS.json').write_text(json.dumps(groups,indent=2));ids=[r['index'] for g in groups for r in g['rows'] if r['recovered']];assert ids
s=(old/'classify_locked.py').read_text().replace('/root/rml24_locked_detection_research_20261101','/root/rml24_single_repeat_precision_rf_20261101');s=s.replace('import candidate_two_dc as recovery','import single_repeat_recovery_ref as recovery').replace('recovery.recover(np.load','recovery.recover_auto(np.load');s=re.sub(r'^selected=.*$', 'selected='+repr(ids),s,flags=re.M);f=p/'classify_single_precision.py';f.write_text(s)
remote='/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/classify_single_precision.py';ps(['E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(f),'-Remote',remote]);(p/'CLASS_START.txt').write_text(board('nohup /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 '+remote+' > /root/single_precision_class_20261101.log 2>&1 < /dev/null &'))
for _ in range(30):
 t=board('test -f /root/rml24_single_repeat_precision_rf_20261101/CLASSIFICATION_RESULT.json && echo CLASS_DONE',2)
 if re.search(r'(?:^|[\r\n])CLASS_DONE',t):break
 time.sleep(3)
else:raise RuntimeError('classification result absent')
command='python3 -c '+repr('import pathlib,gzip,base64; p=pathlib.Path("/root/rml24_single_repeat_precision_rf_20261101/CLASSIFICATION_RESULT.json"); print("PREC_BEGIN"+base64.b64encode(gzip.compress(p.read_bytes())).decode()+"PREC_END")')
t=board(command,5);(p/'CLASS_EXPORT.txt').write_text(t);m=re.search(r'(?:^|[\r\n])PREC_BEGIN([A-Za-z0-9+/=\s]+)PREC_END',t);assert m;v=json.loads(gzip.decompress(base64.b64decode(re.sub(r'\s','',m[1]))));assert v['guard_clean'];(p/'CLASSIFICATION_RESULT.json').write_text(json.dumps(v,indent=2));pred={r['index']:r['prediction']['pred'] for r in v['rows']};summary=[]
for g in groups:
 expected=int(g['file'][:2]);rs=g['rows'];r=dict(file=g['file'],captures=len(rs),old_detector_correct=sum(x['old_accepted'] and pred.get(x['index'])==expected for x in rs),new_detector_correct=sum(x['new_accepted'] and pred.get(x['index'])==expected for x in rs),recovered_correct=sum(pred.get(x['index'])==expected for x in rs),predictions=[dict(index=x['index'],pred=pred.get(x['index'])) for x in rs]);summary.append(r);print(r,flush=True)
health=board('systemctl is-active rml24-integrated; readlink -f /opt/rml24-integrated/current',3);(p/'RESTORED_SERVICE.txt').write_text(health);assert re.search(r'(?:^|[\r\n])active',health)
(p/'SCORE.json').write_text(json.dumps(dict(scope='Targeted development comparison; 24 pre-existing class0 waveforms, same-source RF coverage; not independent formal regression; no deployment',clock_drift_ns=drift,rows=summary,guard_clean=True),indent=2));print('ACTUAL_SINGLE_REPEAT_DIAGNOSTIC_COMPLETE_NOT_DEPLOYED',flush=True)
