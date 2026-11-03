import pathlib
p=pathlib.Path(__file__).parent
s=pathlib.Path('E:/嵌赛/rml24_scan_final_prep1_20261027/pc_runtime/rml24_scan_tx.py').read_text(encoding='utf-8')
assert s.count('connection.settimeout(30)')==1
(p/'ui_interactive_tx.py').write_bytes(s.replace('connection.settimeout(30)','connection.settimeout(180)').encode('utf-8'))
print('UI diagnostic TX waits up to180 seconds for user commands; formal TX remains unchanged')