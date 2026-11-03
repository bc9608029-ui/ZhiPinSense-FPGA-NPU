from pathlib import Path
import subprocess,time,json,socket
out=dict(passed=False)
for attempt in range(90):
 try:
  pid=int(subprocess.check_output(['systemctl','show','rml24-integrated','-p','MainPID','--value']).strip());args=Path('/proc/%d/cmdline'%pid).read_bytes().decode().strip('\0').split('\0');r=Path(args[args.index('--run')+1]);s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect(str(r/'control.sock'));s.sendall(b'GET_TUNING\n');t=s.recv(8192).decode();s.close()
  logs={k:(r/(k+'.log')).read_text(errors='replace') for k in ('npu','ui','rx')};assert 'min_hz=70000000' in t and 'max_hz=6000000000' in t and 'NPU_STREAM_READY' in logs['npu'] and 'UI_FB_READY' in logs['ui'] and 'STANDALONE_READY' in logs['rx'];out=dict(passed=True,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),run=str(r),tuning=t,release=str(Path('/opt/rml24-integrated/current').resolve()));break
 except Exception as e:out=dict(passed=False,error=str(e));time.sleep(1)
Path('/root/rml24_range_expansion_20261101/REBOOT_ACCEPTANCE.json').write_text(json.dumps(out,indent=2));print('WIDE_RANGE_BOOT_ACCEPTANCE '+json.dumps(out),flush=True)
subprocess.run(['systemctl','disable','rml24-range-bootcheck'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
