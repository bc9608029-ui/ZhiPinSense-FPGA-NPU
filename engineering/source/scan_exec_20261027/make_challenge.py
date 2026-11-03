import pathlib,json
root=pathlib.Path(__file__).parent
p=pathlib.Path('E:/嵌赛/rml24_scan_final_prep1_20261027/pc_runtime/rml24_scan_tx.py')
s=p.read_text(encoding='utf-8').replace('parser.add_argument("--center-hz", type=int, default=CENTER_HZ)','parser.add_argument("--center-hz", type=int, default=CENTER_HZ)\n    parser.add_argument("--schedule", type=Path)')
s=s.replace('records = load_manifest(args.manifest)','records = load_manifest(args.manifest)\n    schedule = json.loads(args.schedule.read_text()) if args.schedule else {}')
s=s.replace('buffer = radio.send(frame)','step = schedule.get(str(item["seq"]), {})\n                hz = int(step.get("center_hz", args.center_hz))\n                if int(radio.get(radio.tlo, "frequency")) != hz:\n                    radio.set(radio.tlo, "frequency", hz)\n                buffer = None if step.get("mute", False) else radio.send(frame)')
s=s.replace('radio.stop(buffer)\n                buffer = None','if buffer is not None:\n                    radio.stop(buffer)\n                buffer = None')
(root/'scheduled_tx_diagnostic.py').write_text(s,encoding='utf-8')
base=pathlib.Path('E:/嵌赛/rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest')
m=json.loads((base/'pc_runtime/selftest_manifest_240.json').read_text());t=json.loads((base/'truth/expected_private.json').read_text());tr={r['seq']:r for r in t['records']}
seen=set();chosen=[]
for r in m['records']:
 c=tr[r['seq']]['class_index']
 if c not in seen:seen.add(c);chosen.append(r)
rows=[];truth=[];schedule={}
for i in range(78):
 r=dict(chosen[i%24]);oldseq=r['seq'];r['seq']=i;rows.append(r);tt=dict(tr[oldseq]);tt['seq']=i;truth.append(tt)
 schedule[str(i)]={'center_hz':2397400000 if i<24 or 48<=i<72 else 2403600000,'mute':i>=72}
for name,obj in [('challenge_manifest_78.json',{'records':rows}),('challenge_truth_pc_only.json',{'n':78,'records':truth}),('challenge_schedule_pc_only.json',schedule)]:
 (root/name).write_text(json.dumps(obj,indent=2))
print('DIAGNOSTIC_TX_READY')