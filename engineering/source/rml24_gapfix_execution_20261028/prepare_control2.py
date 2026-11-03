from pathlib import Path
p=Path(r'E:\rml24_gapfix_execution_20261028\control_board.py')
s=p.read_text(encoding='utf-8-sig').replace("while b'\\n' not in data:","while b'\\n' not in data or (data.startswith(b'OK accepted') and data.count(b'\\n') < 2):").replace("control_no_tx01","control_no_tx02").replace("DURATION_SEC='150'","DURATION_SEC='240'")
s=s.replace("c.close();v=data.decode();", "c.close();v=data.decode();\n if s.startswith('SET_') and 'OK accepted' in v and ('ERR ' in v or data.count(b'\\n') < 2):raise RuntimeError('Final ACK missing or failed: '+v)\n ")
Path(r'E:\rml24_gapfix_execution_20261028\control_board2.py').write_text(s,encoding='utf-8')
compile(s,'control_board2.py','exec')
