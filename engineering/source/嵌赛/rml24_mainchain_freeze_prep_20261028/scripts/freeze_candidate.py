#!/usr/bin/env python3
"""Create an immutable identity manifest before independent RF validation."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--candidate",type=Path,required=True); ap.add_argument("--model-json",type=Path,required=True)
    ap.add_argument("--model-raw",type=Path,required=True); ap.add_argument("--two-dc",type=Path,required=True); ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args(); files=[a.candidate,a.model_json,a.model_raw,a.two_dc]
    for p in files:
        if not p.is_file(): raise SystemExit(f"MISSING {p}")
    obj={"status":"FROZEN_BEFORE_VALIDATION","files":[{"path":str(p.resolve()),"sha256":sha(p),"bytes":p.stat().st_size} for p in files]}
    a.out.write_text(json.dumps(obj,indent=2)+"\n",encoding="utf-8"); print("CANDIDATE_FREEZE result=PASS files=4")
if __name__=="__main__": main()
