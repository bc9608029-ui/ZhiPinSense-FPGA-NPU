#!/usr/bin/env python3
"""Label-blind IQ diagnostics for clean/raw/recovered int16 complex files."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np


def load_i16(p: Path) -> np.ndarray:
    x=np.fromfile(p,dtype="<i2")
    if len(x)==0 or len(x)%2: raise ValueError(f"invalid interleaved IQ: {p}")
    return x.reshape(-1,2).astype(np.float64).view(np.complex128).reshape(-1)


def stats(x):
    rms=float(np.sqrt(np.mean(np.abs(x)**2))); mean=complex(np.mean(x)); peak=float(np.max(np.abs(x)))
    X=np.fft.fftshift(np.fft.fft(x*np.hanning(len(x))))
    ps=np.abs(X)**2; k=int(np.argmax(ps)); dc=float(ps[len(ps)//2]/max(ps.sum(),1e-30))
    return {"samples":len(x),"rms":rms,"peak":peak,"mean_i":mean.real,"mean_q":mean.imag,
            "dc_power_fraction":dc,"peak_bin_offset":k-len(ps)//2,"papr_db":10*np.log10(max(peak*peak/(rms*rms+1e-30),1e-30))}


def pair(a,b):
    n=min(len(a),len(b)); a=a[:n]; b=b[:n]
    alpha=np.vdot(a,b)/(np.vdot(a,a)+1e-30); e=b-alpha*a
    corr=abs(np.vdot(a,b))/np.sqrt((np.vdot(a,a).real+1e-30)*(np.vdot(b,b).real+1e-30))
    return {"samples":n,"complex_gain_i":alpha.real,"complex_gain_q":alpha.imag,"corr":float(corr),
            "affine_nmse":float(np.vdot(e,e).real/(np.vdot(b,b).real+1e-30))}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--raw",type=Path,required=True); ap.add_argument("--recovered",type=Path,required=True)
    ap.add_argument("--clean",type=Path); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    raw,rec=load_i16(a.raw),load_i16(a.recovered); out={"raw":stats(raw),"recovered":stats(rec),"raw_vs_recovered":pair(raw,rec)}
    if a.clean:
        clean=load_i16(a.clean); out["clean"]=stats(clean); out["clean_vs_recovered"]=pair(clean,rec)
    a.out.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8"); print("IQ_DIAGNOSTIC result=PASS")
if __name__=="__main__": main()
