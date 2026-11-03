from pathlib import Path
import sys,time,json,hashlib,numpy as np
p=Path(__file__).parent/sys.argv[1];p.mkdir(exist_ok=True);sys.path[:0]=['E:/FPGA_Work/rml24_range_expansion_20261101/pc/console'];import tx_core
sys.path.insert(0,'E:/FPGA_Work/rml24_range_expansion_20261101/pc/console/vendor');import pluto_link_probe as link
sys.path.insert(0,'E:/FPGA_Work/rml24_timing_fix_20261031');from timing_contract import pc_monotonic_ns
c=tx_core.defaults();c.update(mode='cycle',real=True);items={x['class_index']:x for x in tx_core.prepare(c)};u=link.scan_usb();assert len(u)==1;r=link.Radio(u[0]);events=[];buf=None
try:
 for ch,key,value in [(r.tx,'hardwaregain',-40),(r.tx,'sampling_frequency',2560000),(r.tx,'rf_bandwidth',18000000),(r.tlo,'frequency',2400000000),(r.tlo,'powerdown',0)]:r.set(ch,key,value)
 time.sleep(5)
 for case in json.loads((p.parent/'FROZEN_PLAN.json').read_text())['cases']:
  r.set(r.tx,'hardwaregain',case['tx_gain_db']);actual_gain=float(r.get(r.tx,'hardwaregain').split()[0]);assert abs(actual_gain-case['tx_gain_db'])<.01;
  n=case['repeats'];item=items[case['class_index']];full=item['frame']
  f=np.concatenate([full[:4096],full[4096:4096+n*1024],full[12288:]]);assert len(f)==8192+n*1024;buf=r.send(f);e=dict(tx_gain_db=case['tx_gain_db'],class_index=case['class_index'],repeats=n,start_qpc_ns=pc_monotonic_ns(),samples=len(f),frame_sha=hashlib.sha256(f.tobytes()).hexdigest(),source_sha=item['source_sha256']);events.append(e);(p/'VARIABLE_TX_EVENTS.json').write_text(json.dumps(events,indent=2));time.sleep(4);r.stop(buf);buf=None;e['end_qpc_ns']=pc_monotonic_ns();(p/'VARIABLE_TX_EVENTS.json').write_text(json.dumps(events,indent=2))
finally:
 if buf is not None:r.stop(buf)
 errors=r.close();(p/'VARIABLE_TX_RESTORE.json').write_text(json.dumps(dict(errors=errors)));assert not errors
print('VARIABLE_TX_COMPLETE')
