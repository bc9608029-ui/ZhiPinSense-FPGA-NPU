import ast,json,pathlib,numpy as np,math
root=pathlib.Path(__file__).parent
src=pathlib.Path(r'E:\FPGA_Work\rml24_fpga_ui_integration_20261031\candidate\rml24_final\runtime\ui_event.py').read_text(encoding='utf-8')
node=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name=='_display_payload')
ns={'np':np,'math':math,'_spectrum_provider':None}
exec('from __future__ import annotations\n'+ast.get_source_segment(src,node),ns)
f=ns['_display_payload']
def payload(z):
 t=np.tile(np.stack([z.real,z.imag]),(8,1,1));return f(t)
n=np.arange(1024);out={}
for k in (80,-80):
 z=np.exp(2j*np.pi*k*n/1024);p=payload(z);m=p['display_measurements'];idx=int(np.argmax(p['spectrum_db_rel_x4']));assert idx==(k+512)//4
 assert abs(m['rms_counts']-1)<1e-12 and abs(m['papr_db'])<1e-10
 out[str(k)]={'peak_display_bin':idx,'centroid_hz':m['spectral_centroid_hz'],'true_tone_hz':k*2500,'papr_db':m['papr_db']}
p=payload(np.zeros(1024,dtype=complex));assert not p['spectrum_valid'];out['zero_invalid']=True
z=np.zeros(1024,dtype=complex);z[1]=1;p=payload(z);assert not p['spectrum_valid'];out['nonzero_unsampled_impulse_invalid']=True
z=np.zeros(1024,dtype=complex);z[0]=1;p=payload(z);assert abs(p['display_measurements']['papr_db']-10*np.log10(1024))<1e-10
out['impulse_papr_db']=p['display_measurements']['papr_db']
z=np.exp(2j*np.pi*80*n/1024);a=payload(z);b=payload(z*0.125);assert a['spectrum_db_rel_x4']==b['spectrum_db_rel_x4'];assert abs(b['display_measurements']['rms_counts']/a['display_measurements']['rms_counts']-.125)<1e-12
out['relative_spectrum_scale_invariant']=True
(root/'results.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
