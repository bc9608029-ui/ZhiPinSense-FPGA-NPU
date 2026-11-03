"""Observe frozen recovery without changing its calculations or model inputs."""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
base=Path('/root/rml24_standalone_execution_20261027/candidate/rml24_final')
sys.path.insert(0,str(base/'board_runtime'))
import standalone_receiver as receiver
original=receiver.recover_frame
root=Path('/root/rml24_mainchain_diagnostic_20261028/diag_gmsk02/evidence')
root.mkdir(parents=True,exist_ok=False)
counter=0
def observed(raw,recover):
    global counter
    index=counter;counter+=1
    stem=root/('%06d'%index)
    iq=np.column_stack([raw.real,raw.imag]).astype('<i2')
    if not np.array_equal(raw,iq[:,0].astype(np.float32)+1j*iq[:,1].astype(np.float32)):
        raise RuntimeError('Raw int16 storage would lose information')
    iq.tofile(str(stem)+'.raw.i16')
    trace=dict(index=index,capture_time_ns=time.time_ns(),monotonic=time.monotonic(),
               raw_samples=len(raw),raw_sha256=hashlib.sha256(iq.tobytes()).hexdigest(),success=False)
    def profile(frame,event,arg):
        if event=='return' and frame.f_code is recover.__code__:
            loc=frame.f_locals
            trace['public_start']=int(loc['s']) if 's' in loc else None
            if arg is not None:
                windows,metadata=arg
                np.save(str(stem)+'.recovered.npy',np.asarray(windows))
                trace['recovery_metadata']={k:float(v) for k,v in metadata.items()}
                for key in ['a','b','at','bt']:
                    if key in loc:trace[key]=[float(np.real(loc[key])),float(np.imag(loc[key]))]
                if 'joint' in loc:trace['joint']=[[float(z.real),float(z.imag)] for z in loc['joint']]
                if 'response' in loc:np.save(str(stem)+'.response.npy',loc['response'])
    old=sys.getprofile()
    def wrapped(y):
        sys.setprofile(profile)
        try:return recover(y)
        finally:sys.setprofile(old)
    try:
        frame=original(raw,wrapped)
        Path(str(stem)+'.inputs.bin').write_bytes(frame.tensor_bytes)
        trace.update(success=True,input_sha256=frame.tensor_sha256)
        return frame
    except Exception as exc:
        trace['error']=type(exc).__name__+': '+str(exc);raise
    finally:
        Path(str(stem)+'.trace.json').write_text(json.dumps(trace,indent=2))
receiver.recover_frame=observed
if __name__=='__main__':raise SystemExit(receiver.main())
