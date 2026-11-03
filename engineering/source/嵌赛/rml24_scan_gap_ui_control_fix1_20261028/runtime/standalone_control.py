"""Local control with hardware application exclusively on the RX thread."""
from __future__ import annotations
import json
import os
import queue
import socketserver
import stat
import threading
from dataclasses import dataclass, field

class RestartAcquisition(Exception):
    pass

@dataclass
class Command:
    number: int
    line: str
    done: threading.Event = field(default_factory=threading.Event)
    response: str = ''
    started: bool = False
    cancelled: bool = False

class Controller:
    def __init__(self, fixed, start, stop, step, minimum, maximum, max_points=101):
        self.lock = threading.RLock()
        self.pending = queue.Queue(maxsize=16)
        self.counter = 0
        self.minimum, self.maximum, self.max_points = minimum, maximum, max_points
        self.state = dict(mode='FIXED', running=True, fixed_hz=fixed,
                          fixed_readback_hz=0, start_hz=start, stop_hz=stop,
                          step_hz=step, actual_lo_hz=0, command_id=0,
                          scan_index=0, scan_points=0, presence='NO_SIGNAL',
                          frame_id=-1, rms_iq=0.0, peak_iq=0.0, energy_iq2=0.0,
                          feature_latency_us=0.0, backend='software')
        self._validate_frequency(fixed)
        self._validate_range(start, stop, step)

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def update(self, **values):
        with self.lock:
            self.state.update(values)

    def _validate_frequency(self, value):
        if not self.minimum <= value <= self.maximum:
            raise ValueError('OUT_OF_RANGE')

    def _validate_range(self, start, stop, step):
        self._validate_frequency(start)
        self._validate_frequency(stop)
        if start >= stop:
            raise ValueError('START_GE_STOP')
        if step <= 0 or step > 2_304_000:
            raise ValueError('STEP_INVALID')
        count = (stop-start+step-1)//step+1
        if count > self.max_points:
            raise ValueError('STEP_INVALID')
        return count

    def validate(self, line):
        fields = line.split()
        if fields in [['START'], ['STOP']]:
            return fields
        if len(fields) == 2 and fields[0] == 'SET_MODE':
            if fields[1] not in ['FIXED', 'BAND_SCAN']:
                raise ValueError('unsupported_mode')
            return fields
        expected = {'SET_FIXED_HZ': 2, 'SET_SCAN_RANGE_HZ': 4}
        if not fields or fields[0] not in expected or len(fields) != expected[fields[0]]:
            raise ValueError('INVALID_NUMBER')
        if any(not x.isascii() or not x.isdecimal() for x in fields[1:]):
            raise ValueError('INVALID_NUMBER')
        values = [int(x) for x in fields[1:]]
        if fields[0] == 'SET_FIXED_HZ':
            self._validate_frequency(values[0])
        else:
            self._validate_range(*values)
        return fields

    def submit(self, line):
        self.validate(line)
        with self.lock:
            self.counter += 1
            c = Command(self.counter, line)
            try:
                self.pending.put_nowait(c)
            except queue.Full:
                raise ValueError('BUSY')
            return c

    def status(self):
        s = self.snapshot()
        mode, running = s['mode'], int(s['running'])
        return ('OK requested_mode=%s requested_running=%d applied_mode=%s '
                'applied_running=%d pending_mode=0 pending_run=0 last_applied_command_id=%d'
                % (mode, running, mode, running, s['command_id']))

    def tuning(self):
        s = self.snapshot()
        s.update(min_hz=self.minimum, max_hz=self.maximum, max_scan_points=self.max_points)
        s['running'] = int(s['running'])
        return 'OK tuning=1 ' + ' '.join('%s=%s' % (k, v) for k, v in s.items())

    def drain(self, lo):
        changed = False
        while True:
            try:
                c = self.pending.get_nowait()
            except queue.Empty:
                break
            with self.lock:
                if c.cancelled:
                    continue
                c.started = True
            before = self.snapshot()
            touched = False
            try:
                f = self.validate(c.line)
                updates = {}
                if f[0] == 'SET_MODE':
                    if f[1] == 'FIXED':
                        touched = True
                        actual = lo.tune(before['fixed_hz'])
                        lo.flush()
                        updates.update(actual_lo_hz=actual, fixed_readback_hz=actual)
                    updates['mode'] = f[1]
                elif f[0] in ['START', 'STOP']:
                    updates['running'] = f[0] == 'START'
                elif f[0] == 'SET_FIXED_HZ':
                    if before['mode'] != 'FIXED':
                        raise ValueError('BUSY')
                    touched = True
                    actual = lo.tune(int(f[1]))
                    lo.flush()
                    updates.update(fixed_hz=int(f[1]), fixed_readback_hz=actual, actual_lo_hz=actual)
                else:
                    updates.update(start_hz=int(f[1]), stop_hz=int(f[2]), step_hz=int(f[3]))
                updates.update(command_id=c.number, scan_index=0)
                self.update(**updates)
                now = self.snapshot()
                if f[0] == 'SET_FIXED_HZ':
                    c.response = ('OK command_id=%d requested_fixed_hz=%d applied_fixed_hz=%d'
                                  % (c.number, now['fixed_hz'], now['fixed_readback_hz']))
                elif f[0] == 'SET_SCAN_RANGE_HZ':
                    c.response = ('OK command_id=%d requested_start_hz=%d requested_stop_hz=%d '
                                  'requested_step_hz=%d scan_points=%d' % (c.number, now['start_hz'],
                                  now['stop_hz'], now['step_hz'], self._validate_range(now['start_hz'], now['stop_hz'], now['step_hz'])))
                else:
                    c.response = 'OK applied command_id=%d %s' % (c.number, c.line)
                changed = True
            except Exception as exc:
                reason = str(exc) if isinstance(exc, ValueError) else 'DEVICE_REJECTED'
                if touched and before['actual_lo_hz']:
                    try:
                        lo.tune(before['actual_lo_hz'])
                    except Exception as restore_error:
                        c.response = 'ERR command_id=%d reason=DEVICE_REJECTED' % c.number
                        c.done.set()
                        raise RuntimeError('LO rollback failed') from restore_error
                c.response = 'ERR command_id=%d reason=%s' % (c.number, reason)
            finally:
                c.done.set()
        return changed

class ControlServer:
    def __init__(self, path, controller):
        self.path, self.controller = path, controller
        self.server = None

    def start(self):
        if os.path.lexists(self.path):
            if not stat.S_ISSOCK(os.lstat(self.path).st_mode):
                raise RuntimeError('Refusing to replace non-socket control path')
            os.unlink(self.path)
        controller = self.controller
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                while True:
                    data = self.rfile.readline(1025)
                    if not data:
                        return
                    try:
                        line = data.decode('ascii').strip()
                        if len(data) > 1024:
                            raise ValueError('INVALID_NUMBER')
                        if line in ['STATUS', 'GET_TUNING']:
                            response = controller.status() if line == 'STATUS' else controller.tuning()
                            self.wfile.write((response+'\n').encode()); self.wfile.flush()
                            continue
                        c = controller.submit(line)
                        self.wfile.write(('OK accepted command_id=%d %s\n' % (c.number, line)).encode()); self.wfile.flush()
                        if not c.done.wait(35):
                            with controller.lock:
                                c.cancelled = not c.started
                            if c.cancelled:
                                response = 'ERR command_id=%d reason=BUSY' % c.number
                            else:
                                # An in-flight hardware write must resolve before a final ACK.
                                c.done.wait()
                                response = c.response
                        else:
                            response = c.response
                    except (ValueError, UnicodeError) as exc:
                        response = 'ERR command_id=0 reason='+str(exc)
                    try:
                        self.wfile.write((response+'\n').encode()); self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return
        class Server(socketserver.ThreadingUnixStreamServer):
            daemon_threads = True
        self.server = Server(self.path, Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        if self.server:
            self.server.shutdown(); self.server.server_close()
        if os.path.lexists(self.path) and stat.S_ISSOCK(os.lstat(self.path).st_mode):
            os.unlink(self.path)
