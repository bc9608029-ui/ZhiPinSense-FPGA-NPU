from pathlib import Path
import subprocess,json
pid=int(subprocess.check_output(['systemctl','show','rml24-integrated','-p','MainPID','--value']).strip());args=Path('/proc/%d/cmdline'%pid).read_bytes().decode().strip('\0').split('\0');r=Path(args[args.index('--run')+1]);children=json.loads((r/'children.json').read_text());alive={}
for c in children:
 f=Path('/proc')/str(c['pid'])/'cmdline';alive[c['role']]=f.exists() and f.read_bytes().decode().strip('\0').split('\0')==list(map(str,c['argv']))
rows=[json.loads(x) for x in (r/'capture/records.jsonl').read_text().splitlines()];valid=[x for x in rows if x.get('candidate',{}).get('finite')];hist={}
for x in valid:
 k=str(x['candidate']['pred']);hist[k]=hist.get(k,0)+1
out=dict(run=str(r),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),alive=alive,total=len(rows),valid=len(valid),pred_counts=hist,method='systemd MainPID argv --run, not filesystem wall time');(r/'POSTDEPLOY_LIVE_STATUS.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
