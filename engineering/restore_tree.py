from pathlib import Path
import argparse,json,hashlib,shutil,os
def native(p):
 return Path("\\\\?\\"+str(p)) if os.name=="nt" and not str(p).startswith("\\\\?\\") else p
p=argparse.ArgumentParser(description="Restore all local source versions from an exact-deduplicated archive")
p.add_argument("--out",required=True);a=p.parse_args();root=Path(__file__).resolve().parent;out=Path(a.out).resolve()
assert not out.exists(),"Output must be a new directory"
rows=json.loads((root/"SOURCE_MAP.json").read_text(encoding="utf8"));out.mkdir(parents=True)
for x in rows:
 src=root/x["stored"];dst=out/x["original"]
 assert dst.resolve().is_relative_to(out)
 assert hashlib.sha256(native(src).read_bytes()).hexdigest()==x["sha256"],x["stored"]
 native(dst.parent).mkdir(parents=True,exist_ok=True);shutil.copyfile(native(src),native(dst))
print("RESTORED",len(rows),"files to",out)
