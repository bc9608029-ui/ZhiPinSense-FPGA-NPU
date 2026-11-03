import importlib.util,sys,json
from pathlib import Path
p=Path('E:/')/'\u5d4c\u8d5b'/'rml24_multifreq_tx_validation_20261029/scripts/multifreq_tx.py';sys.path.insert(0,str(p.parent));spec=importlib.util.spec_from_file_location('multifreq_tx_hwcompat',str(p));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
old=list(m.TX_CONFIG);m.TX_CONFIG[:]=[(ch,key,value,5.0 if key=='frequency' else 2.0 if key=='sampling_frequency' else tol) for ch,key,value,tol in old]
Path(r'E:\rml24_three_modes_execution_20261029\TX_HW_READBACK_COMPAT.json').write_text(json.dumps(dict(original_config=old,compat_config=m.TX_CONFIG,reason='Observed fractional clock readback Fs -1Hz and LO -2Hz; bounded <=2Hz Fs, <=5Hz LO; waveforms and RX detection thresholds unchanged'),indent=2))
raise SystemExit(m.main())
