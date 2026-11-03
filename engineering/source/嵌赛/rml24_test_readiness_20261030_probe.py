"""Read-only connectivity and local USB scan. Never creates an SDR context."""
import ctypes,importlib.util,json,socket,sys,os
from pathlib import Path
root=Path(__file__).parent/'rml24_test_readiness_20261030'
out={}
if '--usb-only' not in sys.argv:
 try:
  with socket.create_connection(('192.168.126.49',22),timeout=5) as s:
   s.settimeout(5);out['ssh_banner']=s.recv(256).decode('ascii',errors='replace').strip()
 except Exception as e:out['ssh_error']=type(e).__name__+': '+str(e)
handles=[]
if '--libiio026' in sys.argv:
 os.environ['LIBIIO_LIBRARY']='D:/radioconda/Library/bin/libiio.dll'
 handles.append(os.add_dll_directory('D:/radioconda/Library/bin'))
try:
 spec=importlib.util.spec_from_file_location('read_only_radio_probe',root/'tx/vendor/pluto_link_probe.py')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 out['pc_usb_uris']=m.scan_usb()
except Exception as e:out['usb_error']=type(e).__name__+': '+str(e)
print(json.dumps(out,indent=2))
Path(__file__).with_suffix('.usb.json' if '--usb-only' in sys.argv else '.json').write_text(json.dumps(out,indent=2),encoding='utf8')
