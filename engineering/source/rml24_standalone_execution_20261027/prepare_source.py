from pathlib import Path
import shutil,hashlib,json
P=Path(__file__).parent;src=Path('E:/嵌赛/rml24_ui_fivepage_prep_20261027/ui_fivepage_candidate');dst=P/'candidate'
shutil.copytree(src,dst,ignore=shutil.ignore_patterns('bin','final_waterfall_fix1','__pycache__','*.host_x86_64'))
shutil.copyfile('E:/scan_exec_20261027/rml24_dualmode_receiver_centered_v2.py',dst/'rml24_final/board_runtime/rml24_dualmode_receiver_centered_v2.py')
for rel,sha in [('recovery/candidate_two_dc.py','e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a'),('runtime/receiver_core.py','cb529824a80e9fa2aea6aaa31375c8d560f117c36b9644862cb459f6c39cd79a')]:assert hashlib.sha256((dst/'rml24_final'/rel).read_bytes()).hexdigest()==sha,rel
print('INDEPENDENT_FIVEPAGE_SOURCE_READY')