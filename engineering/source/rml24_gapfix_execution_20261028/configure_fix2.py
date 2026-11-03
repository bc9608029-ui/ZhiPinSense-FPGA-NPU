from pathlib import Path
import hashlib
r=Path('/root/rml24_gapfix_execution_20261028/candidate_fix2/rml24_final')
p=r/'board_runtime/receiver_repeat_mean_gapfix1.py'
s=p.read_text();old='4d35cf5e27f26d6c1bc06f2dbf961b139931b0998ca3995ce47685af38058293'
assert s.count(old)==1
p.write_text(s.replace(old,hashlib.sha256((r/'board_runtime/standalone_receiver.py').read_bytes()).hexdigest()))
print('FIX2_DEPENDENCY_PINNED')
