import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import numpy as np
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'pc_console'))
import multi_core as core
import multi_worker as worker
from tx_core import defaults, prepare


def config(n=2, real=False):
    c = defaults()
    c.update(real=real, uri='usb:test', initial_mask=(1 << n) - 1, max_seconds=1,
             lanes=[dict(hz=2_400_000_000 + i * 3_600_000,
                         **{'class': [4, 12, 3, 21][i]}, message=0) for i in range(n)])
    return c


class MockRadio:
    def __init__(self, state):
        self.state = state; self.tx = 'tx'; self.tlo = 'tlo'; self.saved = []
        self.buffers = []; self.state['log'].append('open')
    def get(self, ch, key):
        value = self.state['attrs'][(ch, key)]
        if self.state.get('mismatch') and self.saved and key == 'sampling_frequency': return '123'
        if self.state.get('rounding_hz') and self.saved and key == 'sampling_frequency':
            return str(value + self.state['rounding_hz'])
        if self.state.get('attribute_error') and self.saved:
            target, delta = self.state['attribute_error']
            if key == target and any(k == key for _, k, _ in self.saved): return str(value + delta)
        return str(value)
    def set(self, ch, key, value):
        self.saved.append((ch, key, self.state['attrs'][(ch, key)]))
        self.state['attrs'][(ch, key)] = value
    def send(self, z):
        self.state.setdefault('load_muted', []).append(self.state['attrs'][('tlo', 'powerdown')] == 1)
        b = object(); self.buffers.append(b); self.state['log'].append('send')
        if self.state.get('send_fail'): raise RuntimeError('injected buffer push failure')
        return b
    def stop(self, b):
        self.state['log'].append('stop')
        if self.state.get('stop_fail'): raise RuntimeError('injected buffer failure')
        self.buffers.remove(b)
    def close(self):
        self.state['log'].append('close'); self.buffers = []
        for ch, key, old in reversed(self.saved): self.state['attrs'][(ch, key)] = old
        self.saved = []
        return ['injected restore failure'] if self.state.get('restore_fail') else []


def state():
    return dict(log=[], attrs={('tx', 'hardwaregain'): -60, ('tx', 'sampling_frequency'): 2560000,
                              ('tx', 'rf_bandwidth'): 18000000, ('tlo', 'frequency'): 2400000000,
                              ('tlo', 'powerdown'): 1})


class CoreTests(unittest.TestCase):
    def test_actual_assets_two_three_four_all_combinations(self):
        for n in (2, 3, 4):
            waves, plan = core.build(config(n))
            self.assertEqual(len(waves), 1 << n)
            self.assertEqual(plan['per_lane_rate'], 2560000)
            self.assertTrue(all(v['component_peak'] <= 2047 for v in plan['scenes'].values()))
            self.assertTrue(np.all(waves[0] == 0))
            # Synthesized sum must be the exact sum of its independent lanes.
            np.testing.assert_allclose(waves[(1 << n) - 1], sum(waves[1 << i] for i in range(n)), atol=1e-12)

    def test_each_lane_payload_recoverable_from_four_lane_sum(self):
        c = config(4); waves, plan = core.build(c); total = waves[15]
        for i, lane in enumerate(c['lanes']):
            offset = lane['hz'] - plan['tx_lo_hz']
            down = resample_poly(total * np.exp(-2j * np.pi * offset * np.arange(len(total)) /
                                               plan['tx_sample_rate']), 1, 8)
            single = defaults(); single.update(mode='single', class_index=lane['class'], message_index=0)
            frame = prepare(single)[0]['frame']
            # Use payload interior; resampling boundaries are excluded, no labels used for recovery.
            x, y = frame[4112:12272], down[4112:12272]
            corr = abs(np.vdot(x, y)) / np.sqrt(np.vdot(x, x).real * np.vdot(y, y).real)
            self.assertGreater(corr, .995, (i, corr))

    def test_two_lane_matches_frozen_resample_shift(self):
        c = config(2); waves, plan = core.build(c)
        for i, lane in enumerate(c['lanes']):
            single = defaults(); single.update(mode='single', class_index=lane['class'], message_index=0)
            frame = prepare(single)[0]['frame']; up = resample_poly(frame, 4, 1)
            old = up * np.exp(2j * np.pi * (lane['hz'] - plan['tx_lo_hz']) * np.arange(len(up)) / 10240000)
            np.testing.assert_array_equal(waves[1 << i], old)

    def test_invalid_frequency_and_nan_rejected(self):
        for key, value in [('gain_db', float('nan')), ('max_seconds', float('inf')), ('real', 1)]:
            c = config(); c[key] = value
            with self.assertRaises(ValueError): core.build(c)
        for delta in (0, 1000000, 3600001, 8000000):
            c = config(); c['lanes'][1]['hz'] = c['lanes'][0]['hz'] + delta
            with self.assertRaises(ValueError): core.build(c)

    def test_fourth_lane_clipping_rejected_not_normalized(self):
        c = config(4)
        with patch.object(core, 'prepare', return_value=[dict(frame=np.ones(16384) * 5000,
                                                            name='TEST', source_sha256='test')]):
            with self.assertRaisesRegex(ValueError, '不自动归一化'): core.build(c)


class WorkerTests(unittest.TestCase):
    def execute(self, c, s=None, script=None, stop_before=False, scanner=None):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            d = Path(td)
            if stop_before: (d / 'stop.request').touch()
            t = threading.Thread(target=script, args=(d,)) if script else None
            if t: t.start()
            with contextlib.redirect_stdout(io.StringIO()):
                rc = worker.run(c, d, (lambda uri: MockRadio(s)) if s is not None else None,
                                scanner or (lambda: ['usb:test']))
            if t: t.join(4); self.assertFalse(t.is_alive())
            return rc, json.loads((d / 'result.json').read_text(encoding='utf8')), [
                json.loads(x) for x in (d / 'events.jsonl').read_text(encoding='utf8').splitlines()]

    def test_offline_never_imports_radio(self):
        with patch.object(worker, 'load_module', side_effect=AssertionError('device import forbidden')):
            rc, r, _ = self.execute(config())
        self.assertEqual(rc, 0); self.assertEqual(r['restore_status'], 'NOT_APPLICABLE')

    def test_stop_before_start_opens_no_device(self):
        s = state(); rc, r, _ = self.execute(config(real=True), s, stop_before=True)
        self.assertEqual(s['log'], []); self.assertEqual(rc, 0)

    def test_unknown_uri_opens_no_device(self):
        s = state(); rc, r, _ = self.execute(config(real=True), s, scanner=lambda: ['usb:other'])
        self.assertEqual(s['log'], []); self.assertEqual(rc, 1)

    def test_switch_stop_then_restore_and_independent_readback(self):
        def commands(d):
            until = time.monotonic() + 5
            while time.monotonic() < until:
                p = d / 'events.jsonl'
                if p.exists() and 'scene_applied' in p.read_text(encoding='utf8'): break
                time.sleep(.02)
            for seq, mask in [(1, 1), (2, 0), (3, 15)]:
                p = d / 'command.tmp'; p.write_text(json.dumps(dict(seq=seq, mask=mask)), encoding='utf8')
                p.replace(d / 'command.json'); time.sleep(.12)
            (d / 'stop.request').touch()
        c = config(4, True); c['max_seconds'] = 5; s = state(); original = copy.deepcopy(s['attrs'])
        rc, r, ev = self.execute(c, s, commands)
        self.assertEqual(rc, 0); self.assertEqual(s['attrs'], original)
        self.assertEqual(r['restore_status'], 'READBACK_RESTORE_OK')
        self.assertEqual([e['scene'] for e in ev if e['event'] == 'scene_applied'], [15, 1, 0, 15])
        self.assertEqual(s['log'][-3:], ['close', 'open', 'close'])
        self.assertTrue(all(x['ok'] for x in r['restore_readback']))
        self.assertTrue(all(s['load_muted']))

    def test_config_readback_failure_does_not_send_and_restores(self):
        s = state(); original = copy.deepcopy(s['attrs']); s['mismatch'] = True
        rc, r, _ = self.execute(config(real=True), s)
        self.assertEqual(rc, 1); self.assertNotIn('send', s['log']); self.assertEqual(original, s['attrs'])

    def test_one_hz_rate_rounding_accepted_but_two_hz_rejected(self):
        for error, expected_rc in [(-1, 0), (1, 0), (-2, 1), (2, 1)]:
            s = state(); s['rounding_hz'] = error
            rc, r, events = self.execute(config(real=True), s)
            self.assertEqual(rc, expected_rc, (error, r))
            if expected_rc: self.assertNotIn('send', s['log'])
            else: self.assertIn('send', s['log'])
            rate = next(x for x in events if x['event'] == 'readback' and x['key'] == 'sampling_frequency')
            self.assertEqual(rate['tolerance'], 1.0)
            self.assertEqual(rate['absolute_error'], abs(error))

    def test_stop_failure_not_success(self):
        s = state(); s['stop_fail'] = True
        rc, r, _ = self.execute(config(real=True), s)
        self.assertEqual(rc, 1); self.assertEqual(r['restore_status'], 'UNVERIFIED')

    def test_restore_failure_not_success(self):
        s = state(); s['restore_fail'] = True
        rc, r, _ = self.execute(config(real=True), s)
        self.assertEqual(rc, 1); self.assertEqual(r['restore_status'], 'UNVERIFIED')

    def test_send_failure_closes_context_and_restores(self):
        s = state(); original = copy.deepcopy(s['attrs']); s['send_fail'] = True
        rc, r, _ = self.execute(config(real=True), s)
        self.assertEqual(rc, 1); self.assertIn('push failure', r['error'])
        self.assertEqual(s['attrs'], original)
        self.assertEqual(s['log'][-3:], ['close', 'open', 'close'])

    def test_real_silence_opens_no_transmit_buffer(self):
        s = state(); c = config(real=True); c['initial_mask'] = 0
        rc, r, _ = self.execute(c, s)
        self.assertEqual(rc, 0); self.assertNotIn('send', s['log'])
        self.assertEqual(r['restore_status'], 'READBACK_RESTORE_OK')

    def test_invalid_scene_command_stops_and_restores(self):
        def command(d):
            p = d / 'command.tmp'; p.write_text(json.dumps(dict(seq=1, mask=999)), encoding='utf8')
            p.replace(d / 'command.json')
        s = state(); original = copy.deepcopy(s['attrs'])
        rc, r, _ = self.execute(config(real=True), s, command)
        self.assertEqual(rc, 1); self.assertNotIn('send', s['log'])
        self.assertEqual(s['attrs'], original)

    def test_device_context_open_failure_not_success(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            def fail(uri): raise RuntimeError('injected context open failure')
            with contextlib.redirect_stdout(io.StringIO()):
                rc = worker.run(config(real=True), Path(td), fail, lambda: ['usb:test'])
            r = json.loads((Path(td) / 'result.json').read_text(encoding='utf8'))
            self.assertEqual(rc, 1); self.assertIn('context open failure', r['error'])
            self.assertEqual(r['restore_status'], 'NO_ATTRIBUTES_CHANGED')

    def test_all_attribute_tolerance_boundaries(self):
        cases = [('frequency', -2, 0), ('frequency', 100, 0), ('frequency', -101, 1),
                 ('hardwaregain', .25, 1), ('rf_bandwidth', 1, 1), ('powerdown', 1, 1)]
        for key, delta, expected in cases:
            s = state(); s['attribute_error'] = key, delta
            rc, result, events = self.execute(config(real=True), s)
            self.assertEqual(rc, expected, (key, delta, result))
            if expected: self.assertNotIn('send', s['log'])
            else: self.assertIn('send', s['log'])
            self.assertEqual(result['restore_status'], 'UNVERIFIED' if key == 'powerdown' else 'READBACK_RESTORE_OK')

    def test_observed_device_rounding_combination_reaches_send(self):
        s = state(); s['rounding_hz'] = -1; s['attribute_error'] = 'frequency', -2
        rc, result, events = self.execute(config(real=True), s)
        self.assertEqual(rc, 0); self.assertIn('send', s['log'])
        self.assertEqual(result['restore_status'], 'READBACK_RESTORE_OK')
        self.assertEqual(sum(x['event'] == 'readback' for x in events), 5)


if __name__ == '__main__': unittest.main(verbosity=2)
