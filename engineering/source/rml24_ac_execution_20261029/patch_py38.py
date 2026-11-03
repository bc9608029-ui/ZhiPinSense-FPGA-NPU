from pathlib import Path
import hashlib,json,sys
r=Path('/root/rml24_ac_execution_20261029');p=r/'candidate/rml24_final/runtime/multisignal_scan_adapter.py';b=p.read_bytes();old=hashlib.sha256(b).hexdigest();assert old=='95723baedccfbb96e75ca1946cedde084ef91d3903b43b5a8ff6e2439cb13940'
changes=[(b'from typing import Any, Callable',b'from typing import Any, Callable, List, Dict, Tuple'),(b'PsdDetector = Callable[[int, np.ndarray], list[Any]]',b'PsdDetector = Callable[[int, np.ndarray], List[Any]]'),(b'Classifier = Callable[[int, np.ndarray], tuple[list[dict[str, Any]], float]]',b'Classifier = Callable[[int, np.ndarray], Tuple[List[Dict[str, Any]], float]]')]
for a,c in changes:assert b.count(a)==1;b=b.replace(a,c)
p.write_bytes(b);new=hashlib.sha256(b).hexdigest();f=r/'launch_scripts/preflight_deploy.py';s=f.read_text();assert s.count(old)==1;f.write_text(s.replace(old,new));(r/'PY38_TYPE_ALIAS_PATCH.json').write_text(json.dumps(dict(old=old,new=new,scope='Typing aliases only; original preflight retained in delivery; derived strict preflight pins exact changed candidate'),indent=2))
sys.path.insert(0,str(r/'candidate/rml24_final/runtime'));import multisignal_receiver_entry;print('PY38_MULTISIGNAL_IMPORT_PASS')
