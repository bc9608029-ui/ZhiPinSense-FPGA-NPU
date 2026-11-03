from pathlib import Path
import json,gzip,numpy as np
r=Path(r'E:\rml24_three_modes_execution_20261029');rx=json.loads(gzip.decompress((r/'source_rf02_summary.json.gz').read_bytes()));tx=json.loads((r/'tx_source_rf02_pc/transmit_run.json').read_text());clock=json.loads((r/'reacquire_clock.json').read_text(encoding='utf-8-sig'));offset=int(clock['offset_ns']);ph=[]
for e in tx['events']:
 if e['event']=='active':ph.append(dict(phase=e['phase'],start_ns=e['wall_ns']))
 elif e['event']=='stop' and ph:ph[-1]['end_ns']=e['wall_ns']
summary=[]
for p in ph:
 g=[v for v in rx['rows'] if p['start_ns']+2000000000 <= v['time_ns']+offset <= p['end_ns']-500000000]
 d={k:float(np.median([v['band_energy'][k] for v in g])) for k in ['A','B','A_plus_fs','A_minus_fs','B_plus_fs','B_minus_fs']} if g else {}
 row=dict(p,captures=len(g),max_clip=max([v['clip_ratio'] for v in g],default=None),median_band_energy=d)
 if g:row['B_over_A_db']=float(10*np.log10(d['B']/d['A']))
 if p['phase']=='a_only' and g:row['A_image_band_ratios_db']={k:float(10*np.log10(d[k]/d['A'])) for k in ['A_plus_fs','A_minus_fs']}
 if p['phase']=='b_only' and g:row['B_image_band_ratios_db']={k:float(10*np.log10(d[k]/d['B'])) for k in ['B_plus_fs','B_minus_fs']}
 summary.append(row)
result=dict(kind='RF_SOURCE_RELATIVE_BAND_ENERGY_NOT_SPECTRUM_ANALYZER_CALIBRATION',captures=len(rx['rows']),raw_sha_failures=rx['raw_sha_failures'],rx_restore=rx['restore'],tx_config_ok=tx['config_ok'],tx_restore_ok=tx['restore_ok'],tx_restore_errors=tx['restore_errors'],clock_uncertainty_ms=clock['uncertainty_ms'],band_halfwidth_hz=rx['band_halfwidth_hz'],phases=summary)
(r/'SOURCE_RF02_ANALYSIS.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
