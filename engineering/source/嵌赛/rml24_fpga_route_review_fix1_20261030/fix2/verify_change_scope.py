from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
ORIGINAL=Path('F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga')
CANDIDATE=Path('F:/FPGA_Work/smartscan_bram_fix1_20261030/fpga')
EXPECTED={
 'smartscan_integration/rtl/smart_scan_psd_buffers.sv',
 'smartscan_integration/rtl/user_reg_router.sv',
 'smartscan_integration/rtl/pl_ddr_mandatory_core_top_combined_smartscan.sv',
 'smartscan_integration/rtl/user_ddr_read_arbiter.sv',
 'pl_ddr_integration_v1/deps/adapters/async_fifo_gray.sv',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
changed=[];constraints=[]
for directory in ['smartscan_integration/rtl','pl_ddr_integration_v1/deps','pl_ddr_integration_v1/rtl']:
 for old in (ORIGINAL/directory).rglob('*'):
  if not old.is_file() or old.suffix not in {'.sv','.v'}:continue
  rel=old.relative_to(ORIGINAL).as_posix();new=CANDIDATE/rel
  if not new.exists():raise RuntimeError('MISSING_SOURCE '+rel)
  if sha(old)!=sha(new):changed.append(rel)
for old in (ORIGINAL/'pl_ddr_integration_v1').glob('*.xdc'):
 rel=old.relative_to(ORIGINAL).as_posix();constraints.append({'path':rel,'unchanged':sha(old)==sha(CANDIDATE/rel)})
if set(changed)!=EXPECTED:raise RuntimeError('CHANGE_SCOPE_MISMATCH '+str(changed))
if not all(x['unchanged'] for x in constraints):raise RuntimeError('CONSTRAINT_CHANGED')
frozen=[]
for rel in ['npu_base/rtl/edif/AI_Mate.edif','smartscan_integration/netlist/smartscan_fft_1024.edif']:
 frozen.append({'path':rel,'sha256':sha(CANDIDATE/rel),'unchanged':sha(ORIGINAL/rel)==sha(CANDIDATE/rel)})
if not all(x['unchanged'] for x in frozen):raise RuntimeError('FROZEN_NETLIST_CHANGED')
result={'scope_verified':True,'changed_rtl':changed,'constraints':constraints,'frozen_netlists':frozen}
(HERE/'CHANGE_SCOPE.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
