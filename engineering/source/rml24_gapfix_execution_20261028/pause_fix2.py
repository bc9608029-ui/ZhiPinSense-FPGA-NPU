import sys,json,datetime
from pathlib import Path
sys.path.insert(0,r'E:\AMR_Rescue_20261025')
import pluto_link_probe as link
r=Path(r'E:\rml24_gapfix_execution_20261028')
uris=link.scan_usb();assert len(uris)==1,uris
radio=link.Radio(uris[0])
try:
 before=radio.get(radio.tlo,'powerdown')
 n=link.writeattr(radio.tlo,b'powerdown',b'1');assert n>=0,n
 after=radio.get(radio.tlo,'powerdown');assert after=='1',after
 report=dict(uri=uris[0],previous_tx_lo_powerdown=before,tx_lo_powerdown=after,reason='USER_REQUESTED_PAUSE',resume_requires_restore_powerdown_before_tx=True)
 (r/'PAUSE_TX_STATE.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
finally:radio.close()
p=r/'FIX2_FORMAL_PROGRESS.json';v=json.loads(p.read_text());v.update(phase='paused_at_user_request',partial_scan=True,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),baseline_services_restored=True,formal_scan_score_not_produced=True);p.write_text(json.dumps(v,indent=2))
(r/'PAUSE_FIX2.md').write_text('用户要求暂停，已停止本轮PC编排和TX进程，并终止板端Fix2接收器；原UI和接收服务active。定频233/240、missing0有效；扫频中途停止，不得产生完整240结果或据此宣称修复通过。PC发射器被强制终止，原finally未执行；已单独将唯一PC Pluto TX LO powerdown置1并读回确认。恢复测试前须根据PAUSE_TX_STATE.json恢复TX LO powerdown（之前为0），不能直接重跑旧目录。保留所有部分事件、源清单及板端日志。禁止自动继续测试或部署。',encoding='utf-8')
