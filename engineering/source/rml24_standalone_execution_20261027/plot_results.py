import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
r=Path(__file__).parent
names=['OOK','4ASK','8ASK','BPSK','QPSK','8PSK','16PSK','32PSK','16APSK','32APSK','64APSK',
       '128APSK','16QAM','32QAM','64QAM','128QAM','256QAM','AM-SSB-WC','AM-SSB-SC',
       'AM-DSB-WC','AM-DSB-SC','FM','GMSK','OQPSK']
for run,title in [('formal_fixed01','Fixed 2400 MHz'),('formal_scan01','Band scan, TX 2403.6 MHz')]:
    s=json.loads((r/(run+'_score.json')).read_text())
    if s['denominator']!=240:raise RuntimeError('Incomplete denominator')
    matrix=np.zeros((24,25),dtype=int)
    for row in s['rows']:matrix[row['label'],row['pred'] if row['pred']>=0 else 24]+=1
    fig,ax=plt.subplots(figsize=(13,11))
    image=ax.imshow(matrix,cmap='Blues',vmin=0,vmax=10,aspect='equal')
    ax.set_xticks(range(25));ax.set_xticklabels(names+['NO FRAME'],rotation=65,ha='right',fontsize=8)
    ax.set_yticks(range(24));ax.set_yticklabels(names,fontsize=8)
    ax.set_xlabel('Predicted class');ax.set_ylabel('Transmitted class')
    ax.set_title('%s\n%d/240 correct (%.2f%%), missing %d'%(title,s['correct'],100*s['correct']/240,s['missing']))
    for y in range(24):
        for x in range(25):
            if matrix[y,x]:ax.text(x,y,str(matrix[y,x]),ha='center',va='center',fontsize=8,
                                  color='white' if matrix[y,x]>=6 else 'black')
    fig.colorbar(image,ax=ax,shrink=.65,label='Count (10 sources per class)')
    fig.text(.5,.015,'Existing frozen source set; first capture in a fixed time window; not confidence or new-sample generalization.',
             ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.035,1,1))
    fig.savefig(r/(run+'_confusion.png'),dpi=160);plt.close(fig)
print('CONFUSION_FIGURES_COMPLETE')
