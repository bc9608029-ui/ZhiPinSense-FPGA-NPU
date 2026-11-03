"""RX on FPGA board: no labels/source IQ, public-pilot recovery, real NPU IPC."""
import argparse,hashlib,json,socket,time
from pathlib import Path
import numpy as np
from pluto_link_probe import Radio,scan_usb
from pilot_recovery import recover
from ui24_publish import Publisher
LABELS=('OOK','4ASK','8ASK','BPSK','QPSK','8PSK','16PSK','32PSK',
 '16APSK','32APSK','64APSK','128APSK','16QAM','32QAM','64QAM','128QAM','256QAM',
 'AM-SSB-WC','AM-SSB-SC','AM-DSB-WC','AM-DSB-SC','FM','GMSK','OQPSK')

def read_exact(sock,n):
    parts=[]
    while n:
        b=sock.recv(n)
        if not b:raise RuntimeError('NPU closed stream')
        parts.append(b);n-=len(b)
    return b''.join(parts)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--server',default='192.168.126.50')
    ap.add_argument('--port',type=int,default=39012);ap.add_argument('--socket',required=True)
    ap.add_argument('--out',required=True);ap.add_argument('--ui-socket',default='/run/amr_rescue_ui24.sock');args=ap.parse_args()
    out=Path(args.out);out.mkdir(exist_ok=False)
    uris=scan_usb();assert len(uris)==1,uris
    radio=Radio(uris[0]);control=None;npu=None;rows=[];publisher=Publisher(args.ui_socket)
    try:
        radio.config_rx()
        npu=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);npu.settimeout(20);npu.connect(args.socket)
        control=socket.create_connection((args.server,args.port),timeout=30)
        cf=control.makefile('rwb',buffering=0)
        while True:
            cf.write(b'NEXT\n');msg=json.loads(cf.readline())
            if msg.get('done'):break
            seq=msg['seq'];row={'seq':seq};t=time.monotonic()
            try:
                y=radio.receive(65536)
                np.save(out/('%04d.raw.npy'%seq),y)
                cf.write(b'CAPTURED\n');ack=json.loads(cf.readline());assert ack.get('stopped')
                x,meta=recover(y);row.update(meta)
                inputs=np.stack([x.real,x.imag],axis=1).astype('<f4')
                assert inputs.shape==(8,2,1024) and np.isfinite(inputs).all()
                (out/('%04d.inputs.bin'%seq)).write_bytes(inputs.tobytes())
                logits=[]
                for inp in inputs:
                    npu.sendall(inp.tobytes());logits.append(np.frombuffer(read_exact(npu,96),dtype='<f4').copy())
                logits=np.stack(logits);assert np.isfinite(logits).all()
                row.update(pred=int(logits.mean(0).argmax()),predictions=logits.argmax(1).tolist(),
                           input_sha256=hashlib.sha256(inputs.tobytes()).hexdigest(),
                           logits=logits.mean(0).tolist())
                row['label']=LABELS[row['pred']]
            except Exception as e:
                row['error']=str(e)
                # All normal recovery failures occur after CAPTURED acknowledgement.
                if 'ack' not in locals() or not ack.get('stopped'):raise
            row['elapsed_ms']=(time.monotonic()-t)*1000
            row['ui_sent']=publisher.unavailable() if 'error' in row else publisher.result(row)
            rows.append(row)
            (out/'results.json').write_text(json.dumps({'status':'BOARD_RX_REAL_NPU_PUBLIC_PILOT_PROTOTYPE',
                'receiver_has_labels':False,'records':rows},indent=2))
            print(json.dumps({k:v for k,v in row.items() if k in ['seq','pred','label','error','elapsed_ms']}),flush=True)
            ack={}
    finally:
        publisher.close()
        if control:control.close()
        if npu:npu.close()
        errors=radio.close();(out/'restore.json').write_text(json.dumps(errors))
    print('BOARD_RX_COMPLETE',len(rows),flush=True)
if __name__=='__main__':main()
