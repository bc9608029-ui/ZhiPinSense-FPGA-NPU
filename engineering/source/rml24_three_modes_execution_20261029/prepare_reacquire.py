from pathlib import Path
r=Path(r'E:\rml24_three_modes_execution_20261029');s=(r/'single_signal_tx.py').read_text();old=" buffer=radio.send(build_frame(data,public.train,public.tail));start=time.time_ns();print('SINGLE_TX_STARTED',start,flush=True);time.sleep(300)";assert s.count(old)==1
new=""" events=[]
 for name,active,seconds in [('signal_before',True,60),('muted',False,35),('signal_after',True,60)]:
  if active:buffer=radio.send(build_frame(data,public.train,public.tail))
  event=dict(phase=name,start_ns=time.time_ns(),active=active,seconds=seconds);events.append(event);(r/'reacquire01_events_private.json').write_text(json.dumps(events,indent=2));print('PHASE_STARTED',event,flush=True)
  time.sleep(seconds)
  if buffer is not None:radio.stop(buffer);buffer=None
  event['end_ns']=time.time_ns();(r/'reacquire01_events_private.json').write_text(json.dumps(events,indent=2))"""
s=s.replace(old,new).replace('single_signal01_restore.json','reacquire01_restore.json');(r/'reacquire_tx.py').write_text(s);compile(s,'reacquire_tx.py','exec')
