from pathlib import Path
import hashlib,json
r=Path('/root/rml24_ac_execution_20261029');b=r/'candidate/board_package';changes=[]
for name,old,new in [('frequency_control.hpp',"if(!out.empty() && out.back()=='.') out.pop_back(); return out;","if(!out.empty() && out.back()=='.') { out.pop_back(); }"+chr(10)+'        return out;'),('target_list_rml24_parse.hpp','namespace detail {','namespace targets_detail {')]:
 p=b/name;data=p.read_bytes();s=data.decode();assert s.count(old)==1;s=s.replace(old,new)
 if name.startswith('target_list'):s=s.replace('detail::JsonReader','targets_detail::JsonReader').replace('// namespace detail','// namespace targets_detail')
 p.write_text(s);changes.append(dict(file=name,before=hashlib.sha256(data).hexdigest(),after=hashlib.sha256(p.read_bytes()).hexdigest()))
(r/'CPP_COMPAT_PATCH.json').write_text(json.dumps(changes,indent=2));print('CPP_PATCH_APPLIED')
