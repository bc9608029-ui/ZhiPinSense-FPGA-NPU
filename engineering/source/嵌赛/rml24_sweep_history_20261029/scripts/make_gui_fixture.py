from pathlib import Path
import sys,json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'candidate/rml24_final/runtime'))
from ui_event import build_ui_event,build_board_ui_result
t=np.zeros((8,2,1024),dtype='<f4')
n=np.arange(1024);t[:,0,:]=np.cos(2*np.pi*n/16);t[:,1,:]=np.sin(2*np.pi*n/16)
rows=[]
for i in range(12):
    logits=np.zeros(24);logits[i%24]=5
    e=build_ui_event(i,dict(pred=i%24,finite=True,mean_logits=logits.tolist()),display_tensor=t)
    mode=['FIXED','BAND SCAN','CONTINUOUS SCAN'][i%3]
    r=build_board_ui_result(e,center_hz=2400000000+i*100000,work_mode=mode)
    rows.append(json.dumps(r))
(ROOT/'evidence/gui_frames.jsonl').write_text('\n'.join(rows)+'\n',encoding='utf-8')
print('GUI_FIXTURE 12 synthetic results (not RF)')
