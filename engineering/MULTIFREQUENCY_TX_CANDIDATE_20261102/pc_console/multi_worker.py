"""Interactive dual TX worker. No IIO import in offline sessions."""
from pathlib import Path
import argparse
import json
import math
import sys
import time
from multi_core import build
from tx_core import ROOT, BW, load_module

# Match existing per-attribute contracts; never apply one generic tolerance.
CONFIG_TOLERANCES = dict(hardwaregain=.01, sampling_frequency=1.0,
                         frequency=100.0, rf_bandwidth=.5, powerdown=0.0)


def run(c, directory, radio_factory=None, scanner=None):
    directory = Path(directory)
    waves, plan = build(c)
    (directory / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf8')
    events = (directory / 'events.jsonl').open('a', encoding='utf8')
    def emit(event, **kw):
        row = dict(event=event, time_ns=time.time_ns(), monotonic_ns=time.monotonic_ns(), **kw)
        line = json.dumps(row, ensure_ascii=False, allow_nan=False)
        events.write(line + '\n'); events.flush()
        print(line, flush=True)
    radio = None; buffer = None; snapshots = []; errors = []; checks = []; failure = None
    factory = radio_factory; current = 0; changes = 0; last_seq = -1
    deadline = time.monotonic() + c['max_seconds']
    def stopping():
        return (directory / 'stop.request').exists() or time.monotonic() >= deadline
    try:
        emit('prepared', real=c['real'], plan=plan)
        if not stopping() and c['real']:
            if factory is None:
                link = load_module('dual_tx_radio', ROOT / 'vendor/pluto_link_probe.py')
                factory, scanner = link.Radio, link.scan_usb
            if scanner is None or c['uri'] not in scanner():
                raise ValueError('指定TX URI不在当前枚举结果中；未自动选择设备')
            radio = factory(c['uri'])
            attrs = [('tlo', 'powerdown', 1), ('tx', 'hardwaregain', c['gain_db']),
                     ('tx', 'sampling_frequency', plan['tx_sample_rate']), ('tx', 'rf_bandwidth', BW),
                     ('tlo', 'frequency', plan['tx_lo_hz'])]
            for role, key, value in attrs:
                snapshots.append((role, key, float(radio.get(getattr(radio, role), key).split()[0])))
            for role, key, value in attrs:
                if stopping(): break
                ch = getattr(radio, role)
                radio.set(ch, key, value)
                actual = float(radio.get(ch, key).split()[0])
                # The previously frozen dual-TX script allows 1 Hz for sample-rate
                # attribute rounding. At 10.24 MS/s this is <0.1 ppm, not a new rate.
                tol = CONFIG_TOLERANCES[key]
                emit('readback', role=role, key=key, requested=value, actual=actual,
                     absolute_error=abs(actual-value) if math.isfinite(actual) else None,
                     tolerance=tol)
                if not math.isfinite(actual) or abs(actual - value) > tol:
                    raise RuntimeError('硬件配置回读不一致: ' + key)
        emit('ready', real=c['real'])
        pending = dict(seq=0, mask=c['initial_mask'])
        while not stopping():
            path = directory / 'command.json'
            if path.exists():
                pending = json.loads(path.read_text(encoding='utf8'))
            seq = pending['seq']; scene = pending['mask']
            if type(seq) is not int or type(scene) is not int or scene not in waves:
                raise ValueError('场景命令无效')
            if seq > last_seq:
                if radio is not None:
                    radio.set(radio.tlo, 'powerdown', 1)
                    if float(radio.get(radio.tlo, 'powerdown').split()[0]) != 1:
                        raise RuntimeError('切换前TX静默回读失败')
                if buffer is not None:
                    radio.stop(buffer); buffer = None
                if scene != 0 and radio is not None:
                    buffer = radio.send(waves[scene])
                    radio.set(radio.tlo, 'powerdown', 0)
                    if float(radio.get(radio.tlo, 'powerdown').split()[0]) != 0:
                        raise RuntimeError('TX启用回读失败')
                current = scene; last_seq = seq; changes += 1
                emit('scene_applied', seq=seq, scene=scene, real=c['real'],
                     device_sha256=plan['scenes'][str(scene)]['device_sha256'])
            time.sleep(.05)
    except Exception as exc:
        failure = str(exc); emit('error', message=failure)
    finally:
        if radio is not None:
            try:
                radio.set(radio.tlo, 'powerdown', 1)
                if float(radio.get(radio.tlo, 'powerdown').split()[0]) != 1:
                    errors.append('stop mute readback mismatch')
            except Exception as exc: errors.append('stop mute: ' + str(exc))
            try:
                if buffer is not None: radio.stop(buffer)
            except Exception as exc: errors.append('stop: ' + str(exc))
            try: errors.extend(radio.close() or [])
            except Exception as exc: errors.append('restore: ' + str(exc))
            observer = None
            try:
                observer = factory(c['uri'])
                for role, key, expected in snapshots:
                    actual = float(observer.get(getattr(observer, role), key).split()[0])
                    ok = abs(actual - expected) <= (.01 if key == 'hardwaregain' else .5)
                    checks.append(dict(role=role, key=key, expected=expected, actual=actual, ok=ok))
                    if not ok: errors.append('restore readback mismatch: ' + key)
            except Exception as exc: errors.append('restore readback: ' + str(exc))
            finally:
                if observer is not None:
                    try: errors.extend(observer.close() or [])
                    except Exception as exc: errors.append('observer close: ' + str(exc))
        status = ('UNVERIFIED' if errors else 'READBACK_RESTORE_OK' if checks else
                  'NO_ATTRIBUTES_CHANGED') if c['real'] else 'NOT_APPLICABLE'
        result = dict(real=c['real'], error=failure, restore_errors=errors, restore_readback=checks,
                      restore_status=status, changes=changes, last_scene=current, rf_validated=False)
        (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
        emit('finished', **result); events.close()
    return 1 if failure or errors else 0


def main():
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf8')
    p = argparse.ArgumentParser(); p.add_argument('--config', type=Path, required=True)
    a = p.parse_args(); c = json.loads(a.config.read_text(encoding='utf8'))
    try: return run(c, a.config.parent)
    except Exception as exc:
        result = a.config.parent / 'result.json'
        if not result.exists():
            result.write_text(json.dumps(dict(error=str(exc), restore_status='UNVERIFIED', real=c.get('real', False))), encoding='utf8')
        print(json.dumps(dict(event='error', message=str(exc))), flush=True); return 1


if __name__ == '__main__': sys.exit(main())
