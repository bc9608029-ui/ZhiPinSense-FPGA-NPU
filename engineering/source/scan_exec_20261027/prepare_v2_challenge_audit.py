import pathlib
p=pathlib.Path(__file__).parent
for source,target in [('audit_challenge.py','audit_challenge_v2.py'),('audit_negative_layers.py','audit_negative_layers_v2.py')]:
 s=(p/source).read_text().replace("'challenge78_results.json'","'challenge78_v2_results.json'").replace("'challenge78_audit.json'","'challenge78_v2_audit.json'")
 (p/target).write_bytes(s.encode('utf-8'))
print('Candidate challenge will use exactly the same 72 signal and 6 muted schedule as original')