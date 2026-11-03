import json,datetime
from pathlib import Path
r=Path(r'E:\rml24_gapfix_execution_20261028')
s=json.loads((r/'gapfix_scan01_score.json').read_text())
report={'fix1_fixed':{'correct':233,'denominator':240,'missing':0},'fix1_scan':{'correct':231,'denominator':240,'missing':3},'missing_indices':[v['index'] for v in s['rows'] if v['chosen_frame'] is None],'diagnosis':'Missing indices 146/147/148 coincide with blocking full rescan around frame564 (~21.076sec). Five-miss/1sec hysteresis did not remove blocking sweep.','fix2':'One search grid point per iteration; revisit last successfully recovered LO between search points; only successful frozen recovery establishes lock. Same thresholds/model/twoDC/frames.','status':'DEVELOPMENT_SMOKE_RUNNING_NOT_FORMALLY_VALIDATED','formal_validation_requires_new_user_approval':True,'physical_ui':'User confirmed Fix1 five pages, plots, two modes and four fields normal; keyboard/apply touch acceptance pending; Fix2 UI byte-identical copy.'}
(r/'FIX2_REPAIR_NOTES.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(r/'FIX2_REPAIR_NOTES.md').write_text('''# Fix2 修复工作记录

Fix1新RF：定频233/240、missing0；扫频231/240、missing3，仍DO_NOT_PROMOTE。

缺项为146、147、148。原记录frame564耗时约21.076秒，含11点全扫；前面连续5次漏检。仅提高滞回未解决接收空窗。

Fix2在独立candidate_fix2树将全扫拆为每次一个网格频点，失锁期间在网格点间回访上次成功恢复的LO；只有通过冻结twoDC恢复才建立锁定。原检测0.10/CFO1000Hz、模型、帧和样本不变。源码及SHA另存，不覆盖Fix1。

正在跑24项开发冒烟，不是新240项独立正式验证，也不是未见波形泛化。正式修复后240+240仍按用户此前要求，开始前再次征求同意。

实屏频率键盘和参数应用触控验收尚待完成。正式服务/自启动/位流均未替换。
''',encoding='utf-8')
