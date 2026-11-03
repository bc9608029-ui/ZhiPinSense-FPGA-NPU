from pathlib import Path
r=Path(r'E:\rml24_gapfix_execution_20261028')
s=(r/'replay_gmsk_mean.py').read_text().replace('gmsk_mean_replay02','gmsk_rms_replay03')
s=s.replace("candidate=np.repeat(mean[None,:,:],8,axis=0)","rms=float(np.sqrt(np.mean(mean.astype(np.float64)**2)*2)); mean=(mean/max(rms,1e-12)).astype('<f4'); candidate=np.repeat(mean[None,:,:],8,axis=0)")
(r/'replay_gmsk_rms.py').write_text(s)
s=(r/'run_gmsk_replay.sh').read_text().replace('gmsk_mean_replay02','gmsk_rms_replay03').replace('replay_gmsk_mean.py','replay_gmsk_rms.py')
(r/'run_gmsk_rms.sh').write_bytes(s.replace('\r\n','\n').encode())
