from pathlib import Path
import json,time,zipfile,hashlib,ctypes
base=Path('E:/FPGA_Work');formal=base/'rml24_lockpilot_formal_prep_20261101';linear=base/'rml24_linear_equalization_research_20261101';out=base/'rml24_adaptation_evidence_20261101';out.mkdir(exist_ok=True);deadline=time.monotonic()+10800;k=ctypes.windll.kernel32;k.SetThreadExecutionState(0x80000001)
try:
 while time.monotonic()<deadline:
  try:
   chain=json.loads((linear/'CHAIN_STATUS.json').read_text());audit=json.loads((formal/'monitoring/PERFORMANCE_AUDIT_FINAL.json').read_text())
  except (FileNotFoundError,json.JSONDecodeError):time.sleep(20);continue
  if chain['stage']=='LINEAR_REPLAY_COMPLETE_BASELINE_RESTORED_NOT_DEPLOYED' and audit.get('completed_rounds')==4:break
  if chain['stage'].startswith('BLOCKED'):
   (out/'STATUS.json').write_text(json.dumps(dict(stage='BLOCKED_NO_COMPLETION_PACKAGE',reason=chain['stage'])));raise SystemExit(1)
  time.sleep(20)
 else:raise RuntimeError('completion wait timeout')
 md=formal/'monitoring/PERFORMANCE_AUDIT_FINAL.md'
 if md.exists():
  text=md.read_text();md.write_text(text.replace(chr(92)+'n',chr(10)))
 raw=json.loads((linear/'RESULT.json').read_text())
 mapping=json.loads((linear/'PERSISTENT_MAPPING_PC_ONLY.json').read_text())
 pure=raw.get('pure_cases',[]);pure_rows=[]
 if len(pure)==len(mapping):
  for a,b in zip(mapping,pure):
   assert a['index']==b['index']
   pure_rows.append(dict(a,pred=b['prediction']['pred'],confidence=b['prediction']['confidence'],correct=b['prediction']['pred']==a['expected']))
 (linear/'PERSISTENT_MODEL_AUDIT.json').write_text(json.dumps(dict(scope='Frozen model pure/quantized source diagnostic, not RF or training',complete=len(pure)==len(mapping),rows=pure_rows),indent=2))
 old_single=base/'rml24_single_repeat_precision_rf_20261101';old_rows=json.loads((old_single/'CLASSIFICATION_RESULT.json').read_text())['rows'];truth={r['index']:r for r in json.loads((linear/'MAPPING_PC_ONLY.json').read_text())};old_pred={r['index']:r['prediction']['pred'] for r in old_rows};stats=[]
 for a in raw.get('raw_statistics',[]):
  t=truth[a['index']];stats.append(dict(a,file=t['file'],old_pred=old_pred[a['index']],expected=t['expected'],old_correct=old_pred[a['index']]==t['expected']))
 (linear/'ACTUAL_ADC_RAIL_AUDIT.json').write_text(json.dumps(dict(scope='Exact saved actual1-repeat captures; rail counts can show ADC saturation, absence cannot exclude analog compression',rows=stats),indent=2))
 roots=['rml24_lockpilot_formal_prep_20261101','rml24_locked_detection_research_20261101','rml24_lockpilot_integrated_smoke_20261101','rml24_tx_precision_rf_20261101','rml24_tx_precision_24rf_20261101','rml24_repeat_precision_paired_20261101','rml24_single_repeat_precision_rf_20261101','rml24_repeat_compatibility_research_20261101','rml24_linear_equalization_research_20261101','rml24_dc_offset_concept_research_20261101','rml24_adaptation_research_20261101']
 files=[]
 for root in roots:
  for f in (base/root).rglob('*'):
   if not f.is_file() or '__pycache__' in f.parts:continue
   if f.suffix.lower() not in ('.json','.jsonl','.md','.py','.txt','.log','.gz'):continue
   if f.stat().st_size>8*1024*1024:continue
   files.append(f)
 blobs={f.relative_to(base).as_posix():f.read_bytes() for f in files}
 identity={name:dict(size=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in blobs.items()}
 archive=out/'adaptation_research_and_formal_evidence.zip'
 with zipfile.ZipFile(str(archive),'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,data in blobs.items():z.writestr(name,data)
  z.writestr('FILE_SHA256.json',json.dumps(identity,indent=2))
 with zipfile.ZipFile(str(archive)) as z:
  assert z.testzip() is None
  for name,entry in identity.items():assert hashlib.sha256(z.read(name)).hexdigest()==entry['sha256'],name
 digest=hashlib.sha256(archive.read_bytes()).hexdigest();(out/(archive.name+'.sha256')).write_text(digest+'  '+archive.name+chr(10));score=json.loads((linear/'SCORE.json').read_text());summary=dict(stage='EVIDENCE_PACKAGE_VERIFIED_NOT_DEPLOYMENT',archive=str(archive),sha256=digest,files=len(identity),formal_performance_gates=audit['all_performance_gates'],single_repeat_linear_replay=dict(old_correct=score['old_correct'],new_correct=score['new_correct'],denominator=score['denominator'],regressions=len(score['lost'])),deployed=False)
 (out/'STATUS.json').write_text(json.dumps(summary,indent=2));(out/'README.md').write_text(chr(10).join(['# Adaptation evidence package','','Evidence/research archive, NOT a production deployment package.','All four fresh RF rounds and the queued frozen-NPU single-repeat raw replay finished. Read STATUS.json, formal monitoring/PERFORMANCE_AUDIT_FINAL.json and linear replay/SCORE.json for actual results.','No automatic deployment. Official release remains range_20261101.','Frozen waveform assets, model binaries and bitstream are not included. Source paths and SHAs are retained; replay/radio reproduction needs those external dependencies.','Raw board IQ stays in the documented board research folders.','Synthetic, same-raw replay, actual short RF and formal same-waveform RF are separate evidence scopes.','ZIP member SHA verification and archive SHA passed.'])+chr(10));print(json.dumps(summary),flush=True)
finally:k.SetThreadExecutionState(0x80000000)
