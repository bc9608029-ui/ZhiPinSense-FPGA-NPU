from pathlib import Path
import hashlib,json
r=Path('/root/rml24_ac_execution_20261029');p=r/'candidate/ui_sw/ui_render.cpp';b=p.read_bytes();s=b.decode();old='void draw_kv_row(';assert s.count(old)==1;s=s.replace(old,'[[maybe_unused]] void draw_kv_row(');p.write_text(s);(r/'CPP_UNUSED_PATCH.json').write_text(json.dumps(dict(file=str(p),before=hashlib.sha256(b).hexdigest(),after=hashlib.sha256(p.read_bytes()).hexdigest()),indent=2));print('UNUSED_HELPER_ANNOTATED')
