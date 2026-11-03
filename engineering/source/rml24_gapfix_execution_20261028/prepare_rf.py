from pathlib import Path
r=Path(r'E:\rml24_gapfix_execution_20261028');old=r.parent/'rml24_repeat_mean_validation_20261028'
oldname='rml24_repeat_mean_validation_20261028';newname=r.name
for name in ['run_approved_validation.py','collect.ps1','emit_validation.py','score_validation.py','cleanup_board.py','preflight_board.py']:
 s=(old/name).read_text(encoding='utf-8-sig').replace(oldname,newname)
 if name=='run_approved_validation.py':
  s=s.replace("base='/root/rml24_standalone_execution_20261027/candidate'","base=root+'/candidate'")
  s=s.replace('candidate_fixed02','gapfix_fixed01').replace('candidate_scan01','gapfix_scan01').replace('run_repeat_mean_v1.sh','run_repeat_mean_gapfix1.sh')
 if name=='cleanup_board.py':
  s=s.replace("b'/root/rml24_mainchain_diagnostic_20261028/receiver_repeat_mean_v1.py'", "b'/root/rml24_gapfix_execution_20261028/candidate/rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py'")
  s=s.replace("target='/root/rml24_standalone_execution_20261027/candidate/bin/board_ui_live_rml24_final'", "target='/root/rml24_gapfix_execution_20261028/candidate/bin/board_ui_live_rml24_final'")
 if name=='emit_validation.py':
  s=s.replace("['candidate_fixed01','candidate_fixed02','candidate_scan01']","['gapfix_fixed01','gapfix_scan01']")
 if name=='preflight_board.py':
  s=s.replace('base=Path("/root/rml24_standalone_execution_20261027/candidate/rml24_final")','base=Path("/root/rml24_gapfix_execution_20261028/candidate/rml24_final")')
  s=s.replace("paths=set(Path(n) for n in expected)","paths=set(Path(n) for n in expected)\npaths.update((base.parent/'bin').glob('board_ui_live_rml24_final'))\npaths.update((base.parent/'board_package').glob('*.hpp'))\npaths.update((base.parent/'board_package').glob('*.cpp'))\npaths.update((base.parent/'ui_sw').glob('*.cpp'))\npaths.update((base.parent/'ui_sw').glob('*.hpp'))")
 (r/name).write_text(s,encoding='utf-8')
(r/'APPROVAL.md').write_text('用户于2026-10-28明确要求开始本交接测试，并要求暂时跳过需要看UI的环节。允许独立候选板测和新的定频240、扫频240回归；不部署。实屏验收待完成。原包不修改，候选两处局部修复保留board_patch2.py。',encoding='utf-8')
