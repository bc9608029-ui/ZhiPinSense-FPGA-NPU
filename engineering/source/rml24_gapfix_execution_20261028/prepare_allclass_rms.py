from pathlib import Path
r=Path(r'E:\rml24_gapfix_execution_20261028');o=r.parent/'rml24_mainchain_diagnostic_20261028'
s=(o/'replay_repeat_mean.py').read_text().replace('mean_replay01','allclass_rms_replay04')
s=s.replace("candidate=np.repeat(mean[None,:,:],8,axis=0)","rms=float(np.sqrt(np.mean(mean.astype(np.float64)**2)*2)); mean=(mean/max(rms,1e-12)).astype('<f4'); candidate=np.repeat(mean[None,:,:],8,axis=0)")
(r/'replay_allclass_rms.py').write_text(s)
s=(r/'run_gmsk_replay.sh').read_text().replace('gmsk_mean_replay02','allclass_rms_replay04').replace('replay_gmsk_mean.py','replay_allclass_rms.py')
(r/'run_allclass_rms.sh').write_bytes(s.replace('\r\n','\n').encode())
