from pathlib import Path
import hashlib,json,tarfile,difflib,shutil
r=Path(r'E:\嵌赛\rml24_boot_persistence_20261027');c=r/'candidate';c.mkdir(exist_ok=True);old=(r/'backup/sd_boot_backup/backup/uEnv.txt').read_text(encoding='utf-8');assert hashlib.sha256((r/'backup/sd_boot_backup/backup/uEnv.txt').read_bytes()).hexdigest()=='a13c985eb5031d75ec7069333897cae38944ba5fbadd509828b63e6a48408560'
lines=old.splitlines();replacements={'bootcmd':'run uenvcmd','loadbit':'mmc rescan && fatload mmc 0:1 0x10000000 download.bit && fpga loadb 0 0x10000000 ${filesize}','uenvcmd':'run loadbit && echo RML24_BOOT_PL_LOADED && mmc rescan && fatload mmc 0:1 0x10080000 Image && fatload mmc 0:1 0x11000000 fmqlmp-verify.dtb && booti 0x10080000 - 0x11000000'}
seen=set();new=[]
for line in lines:
 key=line.split('=',1)[0]
 if key in replacements:line=key+'='+replacements[key];seen.add(key)
 new.append(line)
assert seen==set(replacements);new='\n'.join(new)+'\n';(c/'uEnv.txt').write_text(new,encoding='ascii');(r/'evidence/uEnv.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='original/uEnv.txt',tofile='candidate/uEnv.txt')),encoding='utf-8')
shutil.copyfile(r'E:\tmp\stage7_combined_hdmi.bit',c/'download.bit');assert hashlib.sha256((c/'download.bit').read_bytes()).hexdigest()=='22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9'
(c/'startup').mkdir(exist_ok=True)
(c/'startup/check-ui.sh').write_text('''#!/bin/bash
set -euo pipefail
for n in $(seq 1 60); do
 [ -c /dev/udmabuf0 ] && [ -c /dev/mem ] && break
 sleep .5
done
[ -c /dev/udmabuf0 ] && [ -c /dev/mem ]
echo '3950201f64f4575755840df2d98879b5d3e44a109372192366d67a90652adaf6  /opt/rml24-system/bin/board_ui_live_rml24_final' | sha256sum -c -
''',encoding='ascii')
(c/'startup/start-receiver.sh').write_text('''#!/bin/bash
set -euo pipefail
export PATH=/root/miniconda3/envs/torch_v2.0.1_aarch64/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export UI_SOCKET=/run/sdr_amr_ui_rml24_final.sock
for n in $(seq 1 60); do
 [ -S "$UI_SOCKET" ] && break
 sleep .5
done
[ -S "$UI_SOCKET" ]
if pgrep -x npu_stream >/dev/null; then echo 'Another NPU session is active; refusing a duplicate' >&2; exit 1; fi
mkdir -p /var/log/rml24/runs
RUN=/var/log/rml24/runs/$(date -u +%Y%m%dT%H%M%S)-$$
echo "RML24_RECEIVER_ATTEMPT run=$RUN control=192.168.126.50:39012"
exec bash /opt/rml24-system/rml24_final/board_runtime/run_final_receiver.sh --run "$RUN" --legacy-root /root/amr_rescue_20261025 --model-dir /root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16 --control-host 192.168.126.50
''',encoding='ascii')
(c/'rml24-ui.service').write_text('''[Unit]
Description=RML24 verified classification spectrum waterfall and constellation UI
After=local-fs.target systemd-udev-trigger.service
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
WorkingDirectory=/opt/rml24-system
ExecStartPre=/bin/bash /opt/rml24-system/startup/check-ui.sh
ExecStart=/opt/rml24-system/bin/board_ui_live_rml24_final --sock=/run/sdr_amr_ui_rml24_final.sock --ctl-sock=/run/sdr_amr_control_rml24_final.sock --display-refresh-hz=30
Restart=on-failure
RestartSec=3
TimeoutStopSec=15
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
''',encoding='ascii')
(c/'rml24-receiver.service').write_text('''[Unit]
Description=RML24 frozen receiver waiting for PC Pluto transmitter
Requires=rml24-ui.service
After=rml24-ui.service rc-local.service network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
ExecStart=/bin/bash /opt/rml24-system/startup/start-receiver.sh
Restart=always
RestartSec=30
KillSignal=SIGINT
KillMode=control-group
TimeoutStopSec=20

[Install]
WantedBy=multi-user.target
''',encoding='ascii')
(c/'SHA256SUMS.txt').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(c)).replace('\\','/') for p in sorted(c.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt')+'\n',encoding='ascii')
with tarfile.open(r/'candidate_payload.tar.gz','w:gz') as t:
 for p in sorted(c.rglob('*')):
  if p.is_file():t.add(p,arcname=str(p.relative_to(c)).replace('\\','/'))
shutil.copyfile(r/'candidate_payload.tar.gz',r'E:\嵌赛\rml24_stage7_execution_20261027\transfer\boot_candidate_payload.tar.gz')
print('CANDIDATE_PAYLOAD_SHA',hashlib.sha256((r/'candidate_payload.tar.gz').read_bytes()).hexdigest());print((r/'evidence/uEnv.diff').read_text())