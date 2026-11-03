from pathlib import Path
r=Path(r'E:\rml24_gapfix_execution_20261028');old=r.parent/'rml24_mainchain_diagnostic_20261028'
s=(old/'observe_receiver.py').read_text().replace('diag_fixed01/evidence','diag_gmsk02/evidence')
(r/'observe_gmsk.py').write_text(s)
s=(old/'run_diag.sh').read_text().replace('diag_fixed01','diag_gmsk02').replace('observe_receiver.py','observe_gmsk.py').replace('--duration-sec 280','--duration-sec 140')
s=s.replace('test ! -e "$RUN"','test ! -e "$RUN"\nsystemctl stop rml24-receiver\ntrap \'systemctl start rml24-receiver\' EXIT')
s=s.replace('wait "$NPU" 2>/dev/null || true; }','wait "$NPU" 2>/dev/null || true; systemctl start rml24-receiver; }').replace('trap - EXIT','systemctl start rml24-receiver\ntrap - EXIT')
(r/'run_gmsk.sh').write_text(s)
s=(old/'dev_tx.py').read_text().replace('r=Path(__file__).parent','r=Path(__file__).parent.parent/\'rml24_mainchain_diagnostic_20261028\'')
s=s.replace("v['instance']<2","v['class_index'] in [16,19,22]").replace('assert len(rows)==48 and len({v[\'class_index\'] for v in rows})==24','assert len(rows)==15').replace('DEVELOPMENT_TX_COMPLETE n=48','DEVELOPMENT_TX_COMPLETE n=15')
(r/'gmsk_dev_tx.py').write_text(s)
