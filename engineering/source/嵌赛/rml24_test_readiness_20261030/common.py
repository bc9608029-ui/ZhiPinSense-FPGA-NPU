"""Experiment-only contracts; importing this module never opens hardware."""
from pathlib import Path
import hashlib,importlib.util,json,sys

ROOT=Path(__file__).resolve().parent
IDENTITY={
 'model_json':'28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42',
 'model_raw':'c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151',
 'radio':'1b248f8f391976513c35ca54f31d7daef3fa363e2d095940f9ff17d4d60126a2',
 'recovery':'e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a',
 'candidate_bit':'47b9e1fd2154104bb1bf34e247af07db6908f70436e2ec68845d617e47514ccd',
 'rollback_bit':'22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name,path,expected=None):
 p=Path(path)
 if expected and sha(p)!=expected:raise ValueError('Identity mismatch: '+str(p))
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec)
 sys.modules[name]=m;spec.loader.exec_module(m);return m
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
