"""Nonblocking result-only HDMI feed. No labels/ground truth supplied by TX."""
import json,socket,time
import numpy as np
LABELS=('OOK','4ASK','8ASK','BPSK','QPSK','8PSK','16PSK','32PSK',
 '16APSK','32APSK','64APSK','128APSK','16QAM','32QAM','64QAM','128QAM','256QAM',
 'AM-SSB-WC','AM-SSB-SC','AM-DSB-WC','AM-DSB-SC','FM','GMSK','OQPSK')
MODEL_SHA='c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151'
def result_record(row):
    logits=np.asarray(row['logits'],dtype=np.float64)
    if logits.shape!=(24,) or not np.isfinite(logits).all():raise ValueError('invalid logits')
    probs=np.exp(logits-logits.max());probs/=probs.sum()
    pred=int(logits.argmax())
    if row['pred']!=pred:raise ValueError('prediction/logits mismatch')
    return dict(type='result',version='rml24-chain-v1',model_mode='RML24-BF16-RAW',
      frame_id=int(row['seq'])+1,timestamp_us=time.monotonic_ns()//1000,
      class_count=24,argmax_idx=pred,argmax_class=LABELS[pred],raw_24_top1=pred,
      merged_23_top1=-1,deployment_mode='RAW24_UNMERGED',expert_enabled=False,
      expert_result='NOT_RUN',probabilities=probs.tolist(),confidence=float(probs[pred]),
      snr_db=None,quality=0.0,model_sha=MODEL_SHA,mock=False,source='SDR',
      e2e_us=float(row['elapsed_ms'])*1000,preprocess_us=0,classify_us=0,
      overflow=False,dropped=False,discontinuity=False,short_frame=False,
      presence_state='SIGNAL_PRESENT',level_mode='FIXED',model_scale=1.0,
      rf_gain_db=35.0,work_mode='FIXED',run_state='RUNNING',measurements=None)
class Publisher:
    def __init__(self,path):self.path=path;self.sock=None;self.sent=0;self.dropped=0
    def send(self,record):
        try:
            if self.sock is None:
                self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                self.sock.settimeout(.005);self.sock.connect(self.path)
            self.sock.sendall((json.dumps(record,allow_nan=False,separators=(',',':'))+'\n').encode())
            self.sent+=1;return True
        except (OSError,ValueError):
            self.dropped+=1;self.close();return False
    def result(self,row):return self.send(result_record(row))
    def unavailable(self):
        return self.send(dict(type='state',work_mode='FIXED',run_state='RUNNING',presence_state='ACQUIRING'))
    def close(self):
        if self.sock:self.sock.close();self.sock=None
