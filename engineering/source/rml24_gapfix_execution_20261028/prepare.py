import zipfile,hashlib,pathlib,subprocess,json
root=pathlib.Path(r'E:\rml24_gapfix_execution_20261028')
p=pathlib.Path(r'E:\嵌赛\rml24_scan_gap_ui_control_fix1_20261028.zip')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='dd6ced609b93c9eceadfb706cac47f047fe2641664930818d975a7bc9cd464a0'
out=root/'delivery'
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 for m in z.infolist():
  target=(out/m.filename).resolve()
  target.relative_to(out.resolve())
 z.extractall(out)
print([str(x) for x in out.iterdir()])
