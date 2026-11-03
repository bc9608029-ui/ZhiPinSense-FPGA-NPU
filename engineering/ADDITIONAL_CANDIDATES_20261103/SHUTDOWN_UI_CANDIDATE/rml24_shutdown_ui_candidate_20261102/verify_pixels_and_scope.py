from pathlib import Path
from PIL import Image
import numpy as np,json,hashlib
R=Path('rml24_shutdown_ui_candidate_20261102');rows=[]
for page in range(5):
 a=np.array(Image.open(R/f'previews/baseline/page_{page}.ppm'));b=np.array(Image.open(R/f'previews/candidate/page_{page}.ppm'))
 mask=np.any(a!=b,axis=2);outside=mask.copy();outside[325:549,650:1256]=False
 if page<4:assert not mask.any(),page
 else:assert not outside.any(),('changed outside mode-detail area',int(outside.sum()))
 rows.append(dict(page=page+1,changed_pixels=int(mask.sum()),unchanged_outside_allowed_area=not outside.any()))
for p in (R/'previews/candidate').glob('*.ppm'):
 Image.open(p).save(p.with_suffix('.png'))
base=json.loads((R/'BASELINE_FILES.json').read_text(encoding='utf8'))
changed=[];added=[]
for p in (R/'release').rglob('*'):
 if not p.is_file() or '__pycache__' in p.parts:continue
 rel=p.relative_to(R/'release').as_posix();sha=hashlib.sha256(p.read_bytes()).hexdigest()
 if rel not in base:added.append(rel)
 elif sha!=base[rel]:changed.append(rel)
allow={'candidate/board_package/board_ui_live_rml24_final.cpp','candidate/ui_sw/ui_render.hpp','candidate/ui_sw/ui_render.cpp'}
assert set(changed)==allow,changed
assert set(added)=={'candidate/board_package/shutdown_action.hpp','candidate/ui_sw/shutdown_ui.hpp'},added
report=dict(status='OFFLINE_PASS_BOARD_PENDING',changed_existing=changed,added=added,
 receiver_model_fpga_and_service_files_unchanged=True,original_files=len(base),
 pixel_comparison=rows,ui_state_tests=16,action_tests=6,legacy_kernel_action_tests=6,
 real_poweroff_executed=False,board_deployed=False)
(R/'OFFLINE_VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2))
