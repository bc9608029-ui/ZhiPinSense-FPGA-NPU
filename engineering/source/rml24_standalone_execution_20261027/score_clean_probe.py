import gzip,json,tarfile
from pathlib import Path
r=Path(__file__).parent
e=json.loads(gzip.decompress((r/'board_evidence.json.gz').read_bytes()))
probe=e['clean_npu_probe'];results=probe['results']
truth=json.loads((r/'clean_npu_probe_truth_PC_ONLY.json').read_text())
with tarfile.open(r/'clean_npu_inputs_label_free.tar.gz') as t:
    manifest=json.loads(t.extractfile('manifest_public.json').read())['records']
if len(results)!=33 or len(truth)!=33:raise RuntimeError('Incomplete clean NPU probe')
rows=[]
for actual,expected,public in zip(results,truth,manifest):
    if actual['index']!=expected['index'] or actual['input_sha256']!=public['input_sha256']:
        raise RuntimeError('Clean probe input/index mismatch')
    rows.append(dict(index=actual['index'],source_file=expected['source_file'],
                     expected=expected['expected'],pred=actual['result']['pred'],
                     correct=expected['expected']==actual['result']['pred']))
summary=dict(kind='CLEAN_INPUT_DIRECT_NPU_DIAGNOSTIC_NOT_RF',n=33,
             correct=sum(v['correct'] for v in rows),
             am_dsb_wc_n=sum(v['expected']==19 for v in rows),
             am_dsb_wc_correct=sum(v['correct'] and v['expected']==19 for v in rows),
             npu_stop=probe['npu_stop'],rows=rows)
(r/'CLEAN_NPU_PROBE_SUMMARY.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))
