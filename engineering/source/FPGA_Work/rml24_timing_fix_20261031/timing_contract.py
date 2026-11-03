"""Wall clocks are metadata only; RF matching uses explicit monotonic clocks."""
import ctypes,sys,time

def pc_monotonic_ns():
 if sys.platform=='win32':
  counter=ctypes.c_longlong();frequency=ctypes.c_longlong()
  if not ctypes.windll.kernel32.QueryPerformanceCounter(ctypes.byref(counter)) or not ctypes.windll.kernel32.QueryPerformanceFrequency(ctypes.byref(frequency)):raise OSError('QPC unavailable')
  return counter.value*1000000000//frequency.value
 return time.monotonic_ns()

def first_capture(events,records,offset_ns,coverage_hz=None):
 out=[]
 for event in events:
  begin=event['start_mono_ns']+1500000000;end=event['end_mono_ns']-300000000
  eligible=[x for x in records if begin<=x['capture_monotonic_ns']+offset_ns<=end]
  if coverage_hz is not None:eligible=[x for x in eligible if x['scan_steps'] and abs(x['scan_steps'][0]['lo_hz']-coverage_hz)<=1152000]
  out.append(min(eligible,key=lambda x:x['capture_monotonic_ns']) if eligible else None)
 return out

def validate_calibration(before,after,max_drift_ns=100000000):
 if before['board_boot_id']!=after['board_boot_id']:raise ValueError('board reboot during RF run')
 if before['clock_id']!='windows-qpc-board-monotonic-v1' or after['clock_id']!=before['clock_id']:raise ValueError('clock contract mismatch')
 if max(before['uncertainty_ns'],after['uncertainty_ns'])>250000000:raise ValueError('clock uncertainty too high')
 drift=after['offset_ns']-before['offset_ns']
 if abs(drift)>max_drift_ns:raise ValueError('clock drift exceeds frozen bound; do not score')
 return drift


def validate_records(records,calibration):
 for row in records:
  if row.get('clock_id')!='board-monotonic-v1' or row.get('boot_id')!=calibration['board_boot_id']:raise ValueError('mixed or missing capture clock identity')
  value=row.get('capture_monotonic_ns')
  if not isinstance(value,int) or value<0 or (row.get('finite') and value==0) or (row.get('scan_steps') and value==0):raise ValueError('missing actual capture monotonic timestamp; scoring forbidden')
 return True
