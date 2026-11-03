import ast,json
from pathlib import Path
class Normalize(ast.NodeTransformer):
 def visit_Assign(self,node):
  if all(isinstance(t,ast.Name) and t.id in ('capture_mono_ns','boot_id','captured_monotonic') for t in node.targets):return None
  return self.generic_visit(node)
 def visit_Call(self,node):
  node=self.generic_visit(node)
  if isinstance(node.func,ast.Name) and node.func.id in ('dict',):node.keywords=[k for k in node.keywords if k.arg not in ('capture_monotonic_ns','clock_id','boot_id','captured_monotonic_ns','confirmed_monotonic_ns')]
  if isinstance(node.func,ast.Attribute) and node.func.attr=='update':node.keywords=[k for k in node.keywords if k.arg not in ('captured_monotonic_ns','confirmed_monotonic_ns')]
  return node
base=Path('/root/rml24_fpga_ui_20261031');out=[]
for rel in ['candidate/rml24_final/board_runtime/standalone_receiver.py','candidate/rml24_final/runtime/continuous_sweep.py']:
 old=Normalize().visit(ast.parse((base/'delivery_guard_persistent'/rel).read_text()));new=Normalize().visit(ast.parse((base/'delivery_release_candidate'/rel).read_text()));assert ast.dump(old)==ast.dump(new),rel;out.append(rel)
print('FINAL_RECEIVER_AND_SWEEP_AST_EQUIVALENCE_PASS '+json.dumps(out))
