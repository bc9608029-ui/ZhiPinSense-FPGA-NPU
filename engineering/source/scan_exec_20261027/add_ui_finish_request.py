import pathlib
p=pathlib.Path(__file__).parent;f=p/'ui_interactive_tx.py';s=f.read_text()
s=s.replace('tx_rows = []','tx_rows = []')
s=s.replace('for item in records:\n                if stream.readline()', 'session_finished = False\n            for item in records:\n                if stream.readline()')
a='                    raise RuntimeError("receiver protocol mismatch before transmit")\n                source_path'
b='''                    raise RuntimeError("receiver protocol mismatch before transmit")
                if (args.out / "finish_requested").exists():
                    stream.write(b'{"done":true}\\n')
                    session_finished = True
                    break
                source_path'''
assert s.count(a)==1;s=s.replace(a,b)
a='''            if stream.readline() != b"NEXT\\n":
                raise RuntimeError("receiver did not request completion")
            stream.write(b'{"done":true}\\n')'''
b='''            if not session_finished:
                if stream.readline() != b"NEXT\\n":
                    raise RuntimeError("receiver did not request completion")
                stream.write(b'{"done":true}\\n')'''
assert s.count(a)==1;s=s.replace(a,b)
s=s.replace('return 0 if len(tx_rows) == len(records) and not restore_errors else 1','return 0 if not restore_errors else 1')
s=s.replace('{"records": tx_rows, "restore_errors": restore_errors}', '{"kind": "UI_INTERACTIVE_DIAGNOSTIC_NOT_ACCURACY", "records": tx_rows, "restore_errors": restore_errors}')
f.write_bytes(s.encode('utf-8'));print('UI_END_REQUEST_READY')