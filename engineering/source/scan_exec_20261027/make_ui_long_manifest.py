import pathlib,json
p=pathlib.Path(__file__).parent;m=json.loads(pathlib.Path('E:/嵌赛/rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/pc_runtime/selftest_manifest_240.json').read_text())['records'];rows=[]
for i in range(2400):
 r=dict(m[i%240]);r['seq']=i;rows.append(r)
(p/'ui_diagnostic_manifest_2400.json').write_text(json.dumps({'kind':'UI_DIAGNOSTIC_REPEAT_NOT_ACCURACY','records':rows}))