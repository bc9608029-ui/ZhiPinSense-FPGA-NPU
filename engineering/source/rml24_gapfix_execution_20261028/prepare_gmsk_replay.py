from pathlib import Path
r=Path(r'E:\rml24_gapfix_execution_20261028');o=r.parent/'rml24_mainchain_diagnostic_20261028'
s=(o/'replay_repeat_mean.py').read_text().replace('diag_fixed01','diag_gmsk02').replace('mean_replay01','gmsk_mean_replay02')
s += '\nprint(json.dumps(dict(pred_histogram={str(k):sum(v["result"]["pred"]==k for v in results) for k in sorted(set(v["result"]["pred"] for v in results))})),flush=True)\n'
(r/'replay_gmsk_mean.py').write_text(s)
s=(o/'run_mean_replay.sh').read_text().replace('mean_replay01','gmsk_mean_replay02').replace('replay_repeat_mean.py','replay_gmsk_mean.py')
s=s.replace('test ! -e "$OUT"','test ! -e "$OUT"\nsystemctl stop rml24-receiver')
s=s.replace('wait "$NPU" 2>/dev/null || true; }','wait "$NPU" 2>/dev/null || true; systemctl start rml24-receiver; }').replace('trap - EXIT','systemctl start rml24-receiver\ntrap - EXIT')
(r/'run_gmsk_replay.sh').write_bytes(s.replace('\r\n','\n').encode())
