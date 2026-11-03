from pathlib import Path
r=Path('/root/rml24_gapfix_execution_20261028/candidate')
p=r/'board_package/frequency_control.hpp'
s=p.read_text();old="if(!out.empty() && out.back()=='.') out.pop_back(); return out;"
assert s.count(old)==1
p.write_text(s.replace(old,"if(!out.empty() && out.back()=='.') { out.pop_back(); }"+chr(10)+"        return out;"))
p=r/'rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py'
s=p.read_text();old="BASE=Path('/root/rml24_standalone_execution_20261027/candidate/rml24_final')"
assert s.count(old)==1
p.write_text(s.replace(old,"BASE=Path(__file__).resolve().parents[1]"))
print('CANDIDATE_ONLY_PATCH_OK')
