"""One controlled TX session; IIO is loaded only with explicit real=True."""
from pathlib import Path
import argparse,json,sys,time,traceback
from tx_core import prepare,load_module,ROOT,FS,BW
from timing_contract import pc_monotonic_ns

if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf8')

def emit(event,**data):
    print(json.dumps(dict(event=event,**data),ensure_ascii=False,allow_nan=False),flush=True)

def run(config,run_dir,radio_factory=None):
    plan=prepare(config)
    run_dir=Path(run_dir);stop=run_dir/'stop.request'
    started=time.monotonic();deadline=started+float(config['max_seconds'])
    def cancelled():return stop.exists() or time.monotonic()>=deadline
    def wait(seconds):
        end=min(time.monotonic()+seconds,deadline)
        while time.monotonic()<end and not stop.exists():time.sleep(min(.05,max(0,end-time.monotonic())))
    radio=None;buffer=None;errors=[];failure=None;count=0;snapshots=[];restore_checks=[];factory=None
    logfile=(run_dir/'events.jsonl').open('a',encoding='utf8')
    def record(event,**data):
        row=dict(event=event,time_ns=time.time_ns(),monotonic_ns=pc_monotonic_ns(),clock_id='windows-qpc',**data)
        logfile.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');logfile.flush()
        emit(event,time_ns=row['time_ns'],monotonic_ns=row['monotonic_ns'],clock_id=row['clock_id'],**data)
    try:
        record('prepared',frames=len(plan),real=config['real'])
        if config['real']:
            factory=radio_factory
            if factory is None:
                link=load_module('frozen_radio',ROOT/'vendor/pluto_link_probe.py');factory=link.Radio
            radio=factory(config['uri'])
            for channel,key,value in [(radio.tx,'hardwaregain',config['gain_db']),
                                      (radio.tx,'sampling_frequency',FS),
                                      (radio.tx,'rf_bandwidth',BW),
                                      (radio.tlo,'frequency',config['center_hz']),
                                      (radio.tlo,'powerdown',0)]:
                if cancelled():return
                snapshots.append(('tx' if channel==radio.tx else 'tlo',key,radio.get(channel,key).split()[0]))
                radio.set(channel,key,value)
                actual=float(radio.get(channel,key).split()[0])
                if abs(actual-float(value)) > (.01 if key=='hardwaregain' else .5):
                    raise RuntimeError(f'设备回读不一致: {key}={actual}, requested={value}')
            record('configured',uri=config['uri'],center_hz=config['center_hz'],gain_db=config['gain_db'])
        while not cancelled():
            item=plan[count%len(plan)]
            if radio is not None:buffer=radio.send(item['frame'])
            record('transmitting' if config['real'] else 'preview',name=item['name'],index=count,
                   source_sha256=item['source_sha256'],center_hz=config['center_hz'])
            wait(float(config['hold_sec']))
            if buffer is not None:
                radio.stop(buffer);buffer=None
            record('muted',index=count);count+=1
            wait(float(config['gap_sec']))
    except Exception as exc:
        failure=str(exc);record('error',message=failure)
    finally:
        if radio is not None:
            try:
                if buffer is not None:radio.stop(buffer)
            except Exception as exc:errors.append('stop: '+str(exc))
            try:errors.extend(radio.close() or [])
            except Exception as exc:errors.append('restore: '+str(exc))
        if radio is not None and snapshots and not errors:
            observer=None
            try:
                observer=factory(config['uri'])
                for role,key,expected in snapshots:
                    actual=observer.get(getattr(observer,role),key).split()[0]
                    ok=abs(float(actual)-float(expected))<=(.01 if key=='hardwaregain' else .5)
                    restore_checks.append(dict(role=role,key=key,expected=expected,actual=actual,ok=ok))
                    if not ok:errors.append('restore readback mismatch: '+role+'.'+key)
            except Exception as exc:errors.append('restore readback: '+str(exc))
            finally:
                if observer is not None:
                    try:errors.extend(observer.close() or [])
                    except Exception as exc:errors.append('observer close: '+str(exc))
        result=dict(real=config['real'],count=count,error=failure,restore_errors=errors,
                    restore_readback=restore_checks,restore_status=('UNVERIFIED' if errors else 'READBACK_RESTORE_OK' if snapshots else 'NO_ATTRIBUTES_CHANGED') if config['real'] else 'NOT_APPLICABLE')
        (run_dir/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        record('finished',**result);logfile.close()
    return 1 if failure or errors else 0

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path);ap.add_argument('--scan',action='store_true');ap.add_argument('--scan-out',type=Path)
    a=ap.parse_args()
    if a.scan:
        try:
            from tx_core import verify_vendor
            verify_vendor();link=load_module('frozen_radio',ROOT/'vendor/pluto_link_probe.py')
            data=dict(event='devices',uris=link.scan_usb(),time_ns=time.time_ns());rc=0
        except Exception as exc:data=dict(event='error',message=str(exc),time_ns=time.time_ns());rc=1
        if a.scan_out:a.scan_out.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
        emit(data.pop('event'),**data);return rc
    if not a.config:ap.error('--config is required for a session')
    c=json.loads(a.config.read_text(encoding='utf8'))
    try:return run(c,a.config.parent)
    except Exception as exc:emit('error',message=str(exc));return 1
if __name__=='__main__':sys.exit(main())
