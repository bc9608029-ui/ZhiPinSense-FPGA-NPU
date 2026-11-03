from pathlib import Path
import hashlib,json,datetime,shutil
HERE=Path(__file__).resolve().parent
checks=[]
for rel,marker in [
 ('tb_router.log','ROUTER_TEST_PASS addresses=262144'),
 ('tb_fifo.log','ALL_FIFO_CASES_PASS'),
 ('tb_arbiter.log','DDR_ARBITER_PASS'),
 ('routed_pspl/xsim.log','TB_SMART_SCAN_PSPL PASS cases=3 faults=2'),
 ('shared_pspl/xsim_retry.log','TB_SMART_SCAN_PSPL PASS cases=3 faults=2')]:
 p=HERE/rel;text=p.read_text(encoding='utf-8',errors='replace')
 passed=marker in text and not any(x in text for x in ['Fatal:','FATAL:','ERROR: [Simtcl'])
 checks.append({'log':rel,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'pass':passed})
if not all(c['pass'] for c in checks):raise RuntimeError('OFFLINE_TEST_FAILED')
if (HERE/'tb_fifo.log').read_text(encoding='utf-8',errors='replace').count('FIFO_EQUIVALENCE_PASS')!=4:
 raise RuntimeError('MISSING_FIFO_CASE')
src=Path('F:/FPGA_Work/codex_bram_review_20261030/fifo_fix2')
dst=HERE/'fifo_synthesis';dst.mkdir(exist_ok=True)
for name in ['original_util.rpt','fixed_util.rpt','original_cells.txt','fixed_cells.txt']:
 shutil.copy2(src/'fifo_synthesis'/name,dst/name)
shutil.copy2(src/'compare_fifo.log',dst/'compare_fifo.log')
if 'FIFO_SYNTH_COMPARISON_PASS' not in (dst/'compare_fifo.log').read_text(encoding='utf-8',errors='replace'):
 raise RuntimeError('SYNTH_COMPARISON_INCOMPLETE')
result={'time':datetime.datetime.now().isoformat(),'state':'OFFLINE_FIX2_TESTS_PASSED_FULL_IMPLEMENTATION_PENDING',
        'checks':checks,'fifo_cases':4,'fpga_programmed':False,'rf_tested':False,
        'scope':json.loads((HERE/'CHANGE_SCOPE.json').read_text(encoding='utf-8'))}
(HERE/'TEST_RECEIPT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(result['state'])
