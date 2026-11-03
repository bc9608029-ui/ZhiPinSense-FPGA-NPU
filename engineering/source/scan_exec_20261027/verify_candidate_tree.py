import pathlib,hashlib,gzip,tarfile,io,json
p=pathlib.Path(__file__).parent;parts=sorted((p/'candidate_archive_parts').glob('candidate_tree.part*'));assert len(parts)==10
b=b''.join(x.read_bytes() for x in parts);sha=hashlib.sha256(b).hexdigest();assert sha=='cbd524d60bd9e66de3520bb5e1a410b69be3ea683d4c056cf18cd7ef7815a4d2'
f=p/'candidate_v2_fourpage_waterfall_tree.tar.gz';f.write_bytes(b);raw=gzip.decompress(b);assert raw[:2]!=b'\x1f\x8b'
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as t:
 names=t.getnames();assert not any('/truth/' in n or 'expected_private' in n or 'selftest_manifest' in n for n in names)
 targets={'ui_fourpage_waterfall/rml24_final/board_runtime/rml24_dualmode_receiver_centered_v2.py':p/'rml24_dualmode_receiver_centered_v2.py','ui_fourpage_waterfall/board_package/board_ui_live_rml24_final.cpp':p/'fourpage_waterfall.cpp'}
 for target,local in targets.items():assert t.extractfile(target).read()==local.read_bytes(),target
r={'sha256':sha,'bytes':len(b),'parts':10,'single_gzip':True,'private_truth_found':False,'key_sources_exact_match':True};(p/'candidate_tree_independent_verify.json').write_text(json.dumps(r,indent=2));(p/(f.name+'.sha256')).write_bytes((sha+'  '+f.name+'\n').encode());print(json.dumps(r))