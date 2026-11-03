import pathlib,json
p=pathlib.Path(__file__).parent
rows=json.loads((p/'challenge78_v2_results.json').read_text())['records'];by={r['seq']:r for r in rows};truth={r['seq']:r for r in json.loads((p/'challenge_truth_pc_only.json').read_text())['records']};schedule=json.loads((p/'challenge_schedule_pc_only.json').read_text());correct=0;invalid=[];missing=[];freq=[]
for seq in range(72):
 r=by.get(seq)
 if r is None:missing.append(seq);continue
 a=r.get('candidate',{});valid=a.get('finite',False) and 0<=a.get('pred',-1)<24
 if not valid:invalid.append(seq)
 correct+=valid and a['pred']==truth[seq]['class_index']
 if 'scan_hit' in r:freq.append(abs(r['scan_hit']['signal_hz']-schedule[str(seq)]['center_hz']))
neg=[]
for seq in range(72,78):
 r=by.get(seq,{});a=r.get('candidate',{});neg.append({'seq':seq,'pass':bool(r) and not a.get('finite',True) and a.get('pred')==-1 and r.get('error')=='NO_PUBLIC_FRAME_IN_SCAN_RANGE','pred':a.get('pred'),'error':r.get('error')})
hops=[]
for seq in [0,24,48]:
 r=by.get(seq,{});steps=r.get('scan_steps',[]);hops.append({'seq':seq,'target_hz':schedule[str(seq)]['center_hz'],'signal_hz':r.get('scan_hit',{}).get('signal_hz'),'rescan':any(not s.get('locked_check',False) for s in steps),'locked_miss_before_rescan':any(s.get('locked_check',False) and not s.get('accepted',False) for s in steps),'elapsed_ms':r.get('elapsed_ms')})
report={'records':len(rows),'signal_denominator':72,'signal_correct':int(correct),'signal_accuracy':correct/72,'signal_missing':missing,'signal_invalid':invalid,'max_signal_frequency_error_hz':max(freq,default=None),'hop_evidence':hops,'muted_denominator':6,'muted_pass':sum(n['pass'] for n in neg),'muted_details':neg,'note':'Predeclared 72 signal and 6 muted diagnostic frames; repeats of 24 sources, not independent new-waveform validation.'}
(p/'challenge78_v2_audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))