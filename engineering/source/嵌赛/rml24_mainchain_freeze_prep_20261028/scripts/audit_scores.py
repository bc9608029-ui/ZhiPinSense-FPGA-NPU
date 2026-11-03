#!/usr/bin/env python3
"""Fail-closed audit of fixed-denominator recognition score JSON files."""
from __future__ import annotations
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path


def load_score(path: Path) -> dict:
    obj=json.loads(path.read_text(encoding="utf-8"))
    rows=obj.get("rows")
    if not isinstance(rows,list): raise ValueError(f"{path}: rows missing")
    den=int(obj.get("denominator",-1))
    if den != len(rows)+int(obj.get("missing",0)):
        raise ValueError(f"{path}: denominator mismatch")
    idx=[int(r["index"]) for r in rows]
    if len(idx)!=len(set(idx)): raise ValueError(f"{path}: duplicate index")
    recomputed=sum(int(r.get("pred",-1))==int(r.get("label",-2)) for r in rows)
    if recomputed != int(obj.get("correct",-1)): raise ValueError(f"{path}: correct mismatch")
    return obj


def summarize(obj: dict) -> dict:
    conf=Counter(); per=defaultdict(lambda:[0,0])
    for r in obj["rows"]:
        y,p=int(r["label"]),int(r.get("pred",-1)); conf[(y,p)]+=1
        per[y][1]+=1; per[y][0]+=int(y==p)
    errors=[{"label":a,"pred":b,"count":n} for (a,b),n in conf.most_common() if a!=b]
    return {"run":obj.get("run"),"denominator":obj["denominator"],"correct":obj["correct"],
            "accuracy":obj["correct"]/obj["denominator"],"missing":obj.get("missing",0),
            "top_confusions":errors[:20],
            "per_class":{str(k):{"correct":v[0],"total":v[1]} for k,v in sorted(per.items())}}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("scores",nargs="+",type=Path); ap.add_argument("--out",type=Path)
    a=ap.parse_args(); report={"status":"PASS","runs":[summarize(load_score(p)) for p in a.scores]}
    text=json.dumps(report,ensure_ascii=False,indent=2)
    if a.out: a.out.write_text(text+"\n",encoding="utf-8")
    print(text)
if __name__=="__main__": main()
