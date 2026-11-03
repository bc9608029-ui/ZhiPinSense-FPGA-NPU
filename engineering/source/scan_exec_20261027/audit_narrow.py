import json,pathlib,numpy as np
root=pathlib.Path(__file__).parent
r=json.loads((root/'scan_narrow_r1_results.json').read_text())['records']
steps=[s for x in r for s in x['scan_steps']]
summary={'n':len(r),'lo_readback_violations':sum(abs(s['actual_lo_hz']-s['requested_lo_hz'])>5000 for s in steps),'full_sweep_rows':sum(any(not s.get('locked_check',False) for s in x['scan_steps']) for x in r),'locked_check_rows':sum(any(s.get('locked_check',False) for s in x['scan_steps']) for x in r),'first_frame_elapsed_ms':r[0]['elapsed_ms'],'locked_elapsed_ms_median':float(np.median([x['elapsed_ms'] for x in r[1:]])),'locked_elapsed_ms_p95':float(np.quantile([x['elapsed_ms'] for x in r[1:]],.95)),'max_abs_signal_frequency_error_hz':max(abs(x['scan_hit']['signal_hz']-2401300000) for x in r if 'scan_hit' in x),'selected_los_hz':sorted({x['scan_hit']['lo_hz'] for x in r if 'scan_hit' in x})}
(root/'scan_narrow_r1_audit.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))