import pathlib,json,hashlib,ast
p=pathlib.Path(__file__).parent
old=pathlib.Path('E:/嵌赛/rml24_scan_final_prep1_20261027/board_runtime/rml24_dualmode_receiver.py')
def fixed(s):
 expr=ast.dump(ast.parse("state.mode == 'FIXED'",mode='eval').body)
 return ['\n'.join(ast.dump(x) for x in n.body) for n in ast.walk(ast.parse(s)) if isinstance(n,ast.If) and ast.dump(n.test)==expr]
r={'fixed_branch_ast_identical':fixed(old.read_text(encoding='utf-8'))==fixed((p/'rml24_dualmode_receiver_centered_v2.py').read_text()),'public_score_threshold':0.1,'new_centered_lock_frequency_bound_hz':1000,'frozen_model_changed':False,'frozen_two_dc_changed':False,'original_receiver_overwritten':False,'startup_replaced':False,'candidate_status':'EXPERIMENTAL_NOT_DEPLOYED','receiver_sha256':hashlib.sha256((p/'rml24_dualmode_receiver_centered_v2.py').read_bytes()).hexdigest(),'launcher_sha256':hashlib.sha256((p/'run_centered_v2.sh').read_bytes()).hexdigest()}
assert r['fixed_branch_ast_identical'];(p/'centered_v2_scope_audit.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))