import pathlib,json,numpy as np
p=pathlib.Path(__file__).parent
out={}
for name,hz in [('scan_narrow_r1',2401300000),('scan_wide_r1',2397400000),('centered_wide_v2',2397400000),('centered_narrow_v2',2401300000)]:
 f=p/(name+'_results.json')
 if not f.exists():continue
 rows=json.loads(f.read_text())['records'];steps=[s for r in rows for s in r.get('scan_steps',[])];hits=[r['scan_hit'] for r in rows if 'scan_hit' in r]
 out[name]={'records':len(rows),'lo_readback_violations':sum(abs(s['actual_lo_hz']-s['requested_lo_hz'])>5000 for s in steps),'full_sweep_rows':sum(any(not s.get('locked_check',False) for s in r.get('scan_steps',[])) for r in rows),'locked_check_rows':sum(any(s.get('locked_check',False) for s in r.get('scan_steps',[])) for r in rows),'first_elapsed_ms':rows[0]['elapsed_ms'],'following_elapsed_median_ms':float(np.median([r['elapsed_ms'] for r in rows[1:]])),'frequency_error_abs_max_hz':max([abs(h['signal_hz']-hz) for h in hits],default=None),'selected_los_hz':sorted({h['lo_hz'] for h in hits}),'centering_rows':sum('public_centering' in r for r in rows)}
(p/'all_scan_audits.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))