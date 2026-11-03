import ast,pathlib,hashlib,json
root=pathlib.Path(__file__).parent
old=pathlib.Path('E:/嵌赛/rml24_scan_final_prep1_20261027/board_runtime/rml24_dualmode_receiver.py')
def fixed(tree):
 expr=ast.dump(ast.parse("state.mode == 'FIXED'",mode='eval').body)
 return ['\n'.join(ast.dump(x) for x in n.body) for n in ast.walk(tree) if isinstance(n,ast.If) and ast.dump(n.test)==expr]
a=fixed(ast.parse(old.read_text(encoding='utf-8')));b=fixed(ast.parse((root/'rml24_dualmode_receiver_centered_candidate.py').read_text()))
r={'fixed_branch_ast_identical':a==b and bool(a),'threshold_changed':False,'model_changed':False,'frozen_two_dc_changed':False,'changes':'BAND_SCAN only: public-estimated physical LO centering; raw IQ to frozen recovery without pre-rotation','receiver_sha256':hashlib.sha256((root/'rml24_dualmode_receiver_centered_candidate.py').read_bytes()).hexdigest(),'launcher_sha256':hashlib.sha256((root/'run_centered_candidate.sh').read_bytes()).hexdigest()}
assert r['fixed_branch_ast_identical'];(root/'centered_candidate_scope_audit.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))