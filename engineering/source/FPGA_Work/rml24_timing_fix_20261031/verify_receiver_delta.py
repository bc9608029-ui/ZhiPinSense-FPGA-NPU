import ast,json
from pathlib import Path
old=Path('/root/rml24_fpga_ui_20261031/delivery_guard_persistent/candidate/rml24_final/board_runtime/standalone_receiver.py');new=Path('/root/rml24_fpga_ui_20261031/delivery_ui_timing/candidate/rml24_final/board_runtime/standalone_receiver.py')
class Normalize(ast.NodeTransformer):
 def visit_Assign(self,node):
  if all(isinstance(t,ast.Name) and t.id in ('capture_mono_ns','boot_id') for t in node.targets):return None
  return self.generic_visit(node)
 def visit_Call(self,node):
  node=self.generic_visit(node)
  if isinstance(node.func,ast.Name) and node.func.id=='dict':node.keywords=[k for k in node.keywords if k.arg not in ('capture_monotonic_ns','clock_id','boot_id')]
  return node
before=Normalize().visit(ast.parse(old.read_text()));after=Normalize().visit(ast.parse(new.read_text()));assert ast.dump(before)==ast.dump(after),'Non-telemetry code changed'
print('RECEIVER_AST_EQUIVALENCE_PASS excluding only added boot/monotonic telemetry')
