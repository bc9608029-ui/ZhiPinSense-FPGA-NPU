import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
r=Path(__file__).parent;old=r.parent/'rml24_standalone_execution_20261027'
names=['OOK','4ASK','8ASK','BPSK','QPSK','8PSK','16PSK','32PSK','16APSK','32APSK','64APSK','128APSK',
       '16QAM','32QAM','64QAM','128QAM','256QAM','AM-SSB-WC','AM-SSB-SC','AM-DSB-WC','AM-DSB-SC','FM','GMSK','OQPSK']
fig,axes=plt.subplots(1,2,figsize=(14,10),sharey=True)
for ax,label,bname,cname in [(axes[0],'FIXED','formal_fixed01','candidate_fixed02'),
                            (axes[1],'BAND SCAN','formal_scan01','candidate_scan01')]:
    b=json.loads((old/(bname+'_score.json')).read_text());c=json.loads((r/(cname+'_score.json')).read_text())
    if b['denominator']!=240 or c['denominator']!=240:raise RuntimeError('Incomplete result')
    bc=[sum(v['label']==i and v['pred']==i for v in b['rows']) for i in range(24)]
    cc=[sum(v['label']==i and v['pred']==i for v in c['rows']) for i in range(24)]
    y=np.arange(24);ax.barh(y-.18,bc,.34,color='#a6adb5',label='Previous RF baseline')
    ax.barh(y+.18,cc,.34,color='#1675ba',label='Frozen candidate, new RF')
    ax.set_xlim(0,10.8);ax.set_xticks(range(0,11,2));ax.set_yticks(y);ax.set_yticklabels(names,fontsize=9)
    ax.set_xlabel('Correct sources per class (out of 10)');ax.grid(axis='x',alpha=.2)
    ax.set_title('%s\nBaseline %d/240; candidate %d/240; missing %d'%(label,b['correct'],c['correct'],c['missing']))
    ax.legend(fontsize=8,loc='lower left')
axes[0].invert_yaxis()
fig.suptitle('Same existing 240 waveforms: previous baseline vs fresh RF candidate validation',fontsize=13)
fig.text(.5,.015,'Fixed time-window first capture; all missing/rejected items count wrong. Not unseen-waveform generalization.',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.04,1,.95));fig.savefig(r/'RF_BASELINE_CANDIDATE_COMPARISON.png',dpi=160)
print('COMPARISON_FIGURE_COMPLETE')
