"""Evidence-derived report; unfinished tests and failed attempts stay visible."""
import datetime,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf8'))
def main():
 rows=[];details={}
 for prefix,folder in [('original_bit',ROOT),('candidate_bit',ROOT/'fpga_execution')]:
  if not folder.exists():continue
  for p in sorted(folder.glob('*/score.json')):
   s=read(p);n=s['denominator'];correct=s['correct'];label=p.parent.name
   rows.append(dict(image=prefix,arm=label,denominator=n,correct=correct,
                    percent={k:round(v*100/n,4) for k,v in correct.items()},valid=s.get('measurement_valid',False)))
   paired={}
   for count in ['1','2','4']:
    flips=[];fixes=[]
    for r in s['rows']:
     baseline=r['pred']['8']==r['label'];candidate=r['pred'][count]==r['label']
     if baseline and not candidate:flips.append(dict(opportunity=r['opportunity'],label=r['label'],prediction=r['pred'][count]))
     if candidate and not baseline:fixes.append(dict(opportunity=r['opportunity'],label=r['label'],prediction8=r['pred']['8']))
    paired[count]=dict(new_errors_vs8=flips,fixes_vs8=fixes)
   details[prefix+'/'+label]=paired
 status={}
 for name in ['STATUS.json','RESUME_STATUS.json','fpga_execution/STATUS.json','fpga_execution/TEST_RESULT.json','fpga_execution/RESTORE_RESULT.json']:
  if (ROOT/name).exists():status[name]=read(ROOT/name)
 result=dict(time=datetime.datetime.now().astimezone().isoformat(),tests=rows,same_capture_repeat_comparison=details,status=status,
             production_promoted=False,scope='Frozen generated-clean IQ, fixed coax configuration; no arbitrary-RF claim',
             shortened_transmit_frame_tested=False,agc_results_do_not_prove_within_frame_gain_constancy=True,
             waveform_sources_reused_across_gain_arms=True,single_session_generalization_proven=False)
 (ROOT/'RESULTS_LATEST.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 text=['# 参数与FPGA测试结果（按证据更新）','',result['time'],'',
       '| 位流 | 测试臂 | 分母 | 1段 | 2段 | 4段 | 8段 | 测量有效 |',
       '|---|---|---:|---:|---:|---:|---:|---|']
 for r in rows:
  text.append('| '+r['image']+' | '+r['arm']+' | '+str(r['denominator'])+' | '+
              ' | '.join(str(r['correct'][k]) for k in ['1','2','4','8'])+' | '+str(r['valid'])+' |')
 text+=['','## 边界','',
 '- 同一raw前1/2/4/8段的离线平均，不是实际缩短TX帧的RF实验。',
 '- 四个增益臂分别重新收发，同一冻结来源集合；不同时间采集，不能把差异全归因于增益。',
 '- 无发射短测只验证采集/恢复动作，不代表已验证静默分类拒绝。',
 '- full45曾因板端空间预检不足退出；失败的TX计划和恢复记录保留，后续补跑不可冒充当时已采到。',
 '- 已完成分数不代表未完成项通过；没有晋级正式参数、替换自启动或写Flash。',
 '- FPGA隔离PSD诊断与正式扫频后端接入是不同验收项，按STATUS和RESTORE_RESULT如实区分。']
 (ROOT/'RESULTS_LATEST.md').write_text('\n'.join(text)+'\n',encoding='utf8')
 print('REPORT_UPDATED rows='+str(len(rows)))
if __name__=='__main__':main()
