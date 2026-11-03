"""Package only completed evidence; never promote a candidate to production."""
import hashlib,json,zipfile
from pathlib import Path
r=Path(__file__).parent
scores={}
for name in ['formal_fixed01','formal_scan01']:
    s=json.loads((r/(name+'_score.json')).read_text())
    if s['denominator']!=240:raise RuntimeError('Incomplete fixed denominator: '+name)
    scores[name]={k:v for k,v in s.items() if k!='rows'}
frozen=json.loads((r/'RF_SOURCE_FREEZE.json').read_text())
for name,sha in frozen.items():
    if hashlib.sha256((r/name).read_bytes()).hexdigest()!=sha:raise RuntimeError('Source changed during RF: '+name)
audit=json.loads((r/'RESULT_AUDIT.json').read_text())
if audit['passed']!=audit['total']:raise RuntimeError('Audit failure: inspect RESULT_AUDIT.json')
baseline=json.loads((r/'BASELINE_AND_SOURCE_AUDIT.json').read_text())
if baseline['passed']!=baseline['total']:raise RuntimeError('Baseline/source mismatch')
clean=json.loads((r/'CLEAN_NPU_PROBE_SUMMARY.json').read_text())
summary=dict(status='BOARD_FUNCTIONAL_TESTED_PRODUCTION_PROMOTION_PENDING',
             dates='2026-10-27 to 2026-10-28 Asia/Shanghai',
             fpga_migration='DEFERRED_BY_USER',stability='DEFERRED_BY_USER',
             software_tests='10/10',control_hardware_tests='19/19',
             ui_fivepage_navigation='USER_CONFIRMED',ui_plots='USER_CONFIRMED',
             formal_rf=scores,audit_passed=audit['passed'],audit_total=audit['total'],
             baseline_source_checks='%d/%d'%(baseline['passed'],baseline['total']),
             clean_input_npu={k:v for k,v in clean.items() if k!='rows'},
             accuracy_issue_resolved=False,baseline_services_restored=True,
             production_startup_changed=False,
             gaps=['screen frequency keypad / tuning progress','complete numeric measurement wiring',
                   'scan discovery list / full-band stitched waterfall',
                   'candidate persistent startup and reboot/coldboot verification'])
(r/'FINAL_TEST_SUMMARY.json').write_text(json.dumps(summary,indent=2))
doc=r/'HANDOFF_STANDALONE_TESTS.md'
text=doc.read_text(encoding='utf-8').replace('`IN_PROGRESS_FORMAL_RF_REGRESSION_RUNNING`',
                          '`BOARD_FUNCTIONAL_TESTED_PRODUCTION_PROMOTION_PENDING`')
text+='\n\n## 2026-10-28 正式回归最终结果\n\n'
for name,s in scores.items():
    text+='- %s：%d/240 = %.2f%%，漏项%d。\n'%(name,s['correct'],100*s['correct']/240,s['missing'])
text+='\n完整口径见 FINAL_TEST_SUMMARY.json。上述未完成功能仍未完成；没有切换正式启动入口。\n'
text+='\n纯净输入直送NPU：%d/%d；AM-DSB-WC %d/%d。该结果不是RF准确率。真实收发中的误识别尚未根治。\n'%(clean['correct'],clean['n'],clean['am_dsb_wc_correct'],clean['am_dsb_wc_n'])
text+='\n完成结果审计%d/%d、模型/源代码/原启动配置审计%d/%d，已恢复原rml24-ui/rml24-receiver服务，候选程序已停止。\n'%(audit['passed'],audit['total'],baseline['passed'],baseline['total'])
doc.write_text(text,encoding='utf-8')
files=[p for p in r.rglob('*') if p.is_file() and '__pycache__' not in p.parts
       and p.suffix not in ['.zip','.pyc'] and p.name!='SHA256SUMS.txt']
hashes={p.relative_to(r).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(r/'SHA256SUMS.txt').write_text(''.join(sha+'  '+name+'\n' for name,sha in sorted(hashes.items())))
files.append(r/'SHA256SUMS.txt')
target=r.parent/'rml24_standalone_tests_20261028.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,r.name+'/'+p.relative_to(r).as_posix())
with zipfile.ZipFile(target) as z:
    if z.testzip():raise RuntimeError('ZIP CRC failed')
    for name,sha in hashes.items():
        if hashlib.sha256(z.read(r.name+'/'+name)).hexdigest()!=sha:raise RuntimeError('ZIP SHA mismatch: '+name)
sha=hashlib.sha256(target.read_bytes()).hexdigest()
target.with_suffix('.zip.sha256').write_text(sha+'  '+target.name+'\n')
print(json.dumps(dict(file=str(target),sha256=sha,bytes=target.stat().st_size,files=len(files))))
