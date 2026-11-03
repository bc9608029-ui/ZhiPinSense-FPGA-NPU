import json
from pathlib import Path
r=Path(r'E:\rml24_gapfix_execution_20261028')
p=r/'FIX2_REPAIR_NOTES.json';v=json.loads(p.read_text());v.update(status='SMOKE24_PASS_PENDING_FORMAL_APPROVAL',smoke={'correct':24,'denominator':24,'missing':0,'max_elapsed_ms':4632.247610000377,'max_search_points_per_record':1,'home_revisit_count':19,'longer_than_10s':0},receiver_sha256='63e3d5feb8cf0d4636105613d2593a9d05029530801846b07a6b17a950973954',baseline_restored=True,logging_note='Smoke runner reused progress counters displaying total240; actual TX plan/events and score contain exactly24. Do not treat progress counters as score.')
p.write_text(json.dumps(v,indent=2),encoding='utf-8')
with (r/'FIX2_REPAIR_NOTES.md').open('a',encoding='utf-8') as f:f.write('\n## 短测试结果\n24/24，missing0；145次接收尝试，每记录最多一个网格探测点，回访旧频点19次，最大处理4.632秒，没有超过10秒的记录。发射/接收恢复错误0，UI发送失败0；原服务已恢复。仅短测试通过，不能宣称正式修复成功。\n\n编排复用遗留进度字段total240，但实际TX清单、事件、判分均恰好24；以score的denominator24为准。保留原日志不改写。\n')
