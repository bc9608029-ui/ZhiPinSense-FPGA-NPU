"""Post-hoc diagnostics only. Never feeds source IQ or labels into recovery."""
import hashlib,json
from pathlib import Path
import numpy as np
r=Path(__file__).parent;run=r/'board/diag_fixed01'
events=[json.loads(x) for x in (r/'diag_fixed01_tx/events_private.jsonl').read_text().splitlines()]
offset=int(json.loads((r/'clock_before.json').read_text(encoding='utf-8-sig'))['offset_ns'])
dataset=r.parent/'嵌赛/amr_rescue_gmsk_candidate_20261026/development_seed4100000'
def stats(z):
    z=np.asarray(z,dtype=np.complex128).reshape(-1);power=float(np.mean(abs(z)**2))
    fft=np.abs(np.fft.fft(z*np.hanning(len(z))))**2;peak=int(fft.argmax())
    return dict(rms=float(np.sqrt(power)),dc_i=float(z.mean().real),dc_q=float(z.mean().imag),
                dc_fraction=float(abs(z.mean())**2/max(power,1e-30)),
                papr_db=float(10*np.log10(max(float(np.max(abs(z)**2))/max(power,1e-30),1e-30))),
                peak_bin=peak,peak_fraction=float(fft[peak]/max(fft.sum(),1e-30)))
def pair(x,y):
    x=np.asarray(x,dtype=np.complex128);y=np.asarray(y,dtype=np.complex128)
    xc=x-x.mean();yc=y-y.mean();alpha=np.vdot(xc,yc)/max(float(np.vdot(xc,xc).real),1e-30)
    beta=y.mean()-alpha*x.mean();alpha0=np.vdot(x,y)/max(float(np.vdot(x,x).real),1e-30)
    e=y-alpha*x-beta;e0=y-alpha0*x
    den=max(float(np.vdot(y,y).real),1e-30)
    corr=abs(np.vdot(x,y))/np.sqrt(max(float(np.vdot(x,x).real)*den,1e-30))
    cross=np.fft.ifft(np.fft.fft(y)*np.conj(np.fft.fft(x)))
    return dict(corr=float(corr),complex_gain=[float(alpha.real),float(alpha.imag)],
                complex_offset=[float(beta.real),float(beta.imag)],
                offset_over_signal_rms=float(abs(beta)/max(float(np.sqrt(np.mean(abs(y)**2))),1e-30)),
                linear_nmse=float(np.vdot(e0,e0).real/den),
                affine_nmse=float(np.vdot(e,e).real/den),best_circular_lag=int(np.abs(cross).argmax()))
rows=[];clean_cache={};shape_fail=[];hash_fail=[]
records=[json.loads(v) for v in (run/'capture/records.jsonl').read_text().splitlines()]
for v in records:
    index=v['frame_id'];stem=run/'evidence'/('%06d'%index)
    trace=json.loads(Path(str(stem)+'.trace.json').read_text())
    if trace['index']!=index:raise RuntimeError('Observation index mismatch')
    rawbytes=Path(str(stem)+'.raw.i16').read_bytes()
    if hashlib.sha256(rawbytes).hexdigest()!=trace['raw_sha256']:hash_fail.append(index)
    capture=v['capture_time_ns']+offset
    tx=next((t for t in events if t['start_ns']+1500000000<=capture<=t['end_ns']-300000000),None)
    row=dict(frame_id=index,pred=v['candidate']['pred'],finite=v['candidate']['finite'],
             event_index=tx['index'] if tx else None,trace=trace)
    if tx:
        row.update(source_file=tx['file'],label=tx['label'],correct=v['candidate']['pred']==tx['label'])
    if trace['success']:
        data=Path(str(stem)+'.inputs.bin').read_bytes()
        if hashlib.sha256(data).hexdigest()!=v['candidate']['input_sha256']:hash_fail.append(index)
        tensor=np.frombuffer(data,dtype='<f4').reshape(8,2,1024)
        z=tensor[:,0,:]+1j*tensor[:,1,:]
        rec=np.load(str(stem)+'.recovered.npy')
        if rec.shape!=(8,1024) or not np.array_equal(z.real,rec.real.astype('<f4')) or not np.array_equal(z.imag,rec.imag.astype('<f4')):
            shape_fail.append(index)
        row['recovered_stats']=stats(z)
        if tx:
            if tx['file'] not in clean_cache:
                data0=(dataset/tx['file']).read_bytes()
                if hashlib.sha256(data0).hexdigest()!=tx['source_sha256']:raise RuntimeError('Clean SHA mismatch')
                q=np.frombuffer(data0,dtype='<f4').reshape(2,1024);clean_cache[tx['file']]=q[0]+1j*q[1]
            clean=clean_cache[tx['file']];row['clean_stats']=stats(clean)
            row['windows']=[pair(clean,w) for w in z]
            row['mean_window']=pair(clean,z.mean(axis=0))
            rawiq=np.frombuffer(rawbytes,dtype='<i2').reshape(-1,2).astype(np.float64)
            raw=rawiq[:,0]+1j*rawiq[:,1];s=trace['public_start'];f=trace['recovery_metadata']['cfo_hz']
            if s is not None and s+10240<=len(raw):
                payload=raw[s+2048:s+10240]*np.exp(-2j*np.pi*f*np.arange(2048,10240)/2560000)
                row['raw_payload_after_cfo']=pair(np.tile(clean,8),payload)
    rows.append(row)
summary=[]
for label in sorted({t['label'] for t in events}):
    group=[v for v in rows if v.get('label')==label]
    by_status={}
    for correct in [True,False]:
        g=[v for v in group if v['correct']==correct and 'mean_window' in v]
        by_status[str(correct)]=dict(n=len(g),
          median_linear_nmse=float(np.median([v['mean_window']['linear_nmse'] for v in g])) if g else None,
          median_affine_nmse=float(np.median([v['mean_window']['affine_nmse'] for v in g])) if g else None,
          median_offset_fraction=float(np.median([v['mean_window']['offset_over_signal_rms'] for v in g])) if g else None,
          median_raw_payload_nmse=float(np.median([v['raw_payload_after_cfo']['affine_nmse'] for v in g if 'raw_payload_after_cfo' in v])) if g else None)
    summary.append(dict(label=label,captures=len(group),errors=sum(not v['correct'] for v in group),groups=by_status))
out=dict(kind='DEVELOPMENT_DIAGNOSTIC_NOT_VALIDATION',records=len(rows),
         raw_hash_failures=hash_fail,tensor_contract_failures=shape_fail,summary=summary,rows=rows)
(r/'IQ_DIAGNOSTIC.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ['rows','summary']},indent=2))
for s in summary:
    if s['errors'] or s['label'] in [19,20,22]:print(json.dumps(s))
