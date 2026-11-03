import json,hashlib
from pathlib import Path
r=Path(r'E:\嵌赛\rml24_stage7_execution_20261027');s1=json.loads((r/'formal_r1_score.json').read_text());s2=json.loads((r/'formal_r2_score.json').read_text());summary=dict(status='STAGE7_RF_TWO_RUNS_COMPLETE_HDMI_PHYSICAL_FAIL',model_changed=False,recovery_changed=False,formal_runs=[{k:s[k] for k in ('correct','total','accuracy','missing_sequences','failure_count')} for s in (s1,s2)],combined_correct=466,combined_total=480,combined_accuracy=466/480,historical_raw_replay=dict(passed=480,total=480),ui_same_tensor=dict(passed=480,total=480),hdmi_physical='User reports black screen; not passed',network_override='Both endpoints use supported explicit 192.168.126.50 argument; .10 alias addition denied by Windows; original IP unchanged',board_root='/root/rml24_stage7_execution_20261027/final',pc_root=str(r));(r/'STAGE7_EXECUTION_SUMMARY.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
text='''# Stage7 实机执行与交接（2026-10-27）

状态：STAGE7_RF_TWO_RUNS_COMPLETE_HDMI_PHYSICAL_FAIL。
本次按HANDOFF_STAGE7执行板端集成和正式收发；识别与UI数据链已验证，实物HDMI仍黑屏。不能标记HDMI_PASS或PROJECT_COMPLETE。

## 已完成

- HANDOFF_STAGE7.md及两个最终部署包SHA全部与用户给定一致。
- PC包独立解包后245条逐文件SHA全部通过；板端包校验通过并组装到新树，不覆盖原工程。
- 板端aarch64原生构建：UI_BUILD_RESULT result=PASS。
- 启动UI：UI_VERSION_CHECK版本0x20230218、ok=YES；UI_FB_READY通过，触摸设备枚举成功。
- 正式candidate-only接收入口；24帧冒烟完成，UI接收24条、拒收0、发送失败0。仅用于验证链路，不代替正式准确率。
- 正式第一轮：234/240=97.50%，缺帧0、恢复/推理失败0；UI成功发送240条。
- 停止并重启UI、重新打开收发及NPU后，正式第二轮：232/240=96.67%，缺帧0、恢复/推理失败0；UI成功发送240条。
- 两轮合计466/480=97.08%。这是同一组240个不同样本的两次真实收发，不是480个不同样本，也不能替代历史独立验证463/480。没有在本次结果上调模型、接收算法、门限或删样本。
- 同源审计：480/480帧，UI星座、频谱重新从保存的模型输入计算，与保存的UI事件一致；输入SHA、NPU预测和UI事件对应一致。
- 历史raw→tensor审计：480/480逐字节一致。历史raw和candidate输入已复制到电脑；归档SHA两端一致，独立读包核验480份raw及480份输入，输入SHA全匹配。
- 两轮正式每轮NPU1920窗口，apply=1/reset=1919/discipline=1；冒烟192窗口。TX/RX状态恢复均无错误，结束后无识别/NPU测试进程残留。
- 板端candidate和模型SHA不变。部署树无truth/private expected/selftest manifest路径；私有真值一直留在电脑。

## HDMI实际情况

用户两次反馈屏幕黑屏，因此实物验收失败。UI日志和版本门成功不等于屏幕成功。
只读导出的实际帧缓冲framebuffer_snapshot.png显示完整识别界面，证明软件已生成画面；该图不是相机拍到的屏幕，也不能据此证明HDMI链路正常。
显示寄存器读取：version=0x20230218，buffer select=1，framebuffer base寄存器0x6020000（字节地址0x30100000），disable_hdmi=0；其他诊断值h_sync44/h_active1920/v_sync5/v_active1080/vtc_enable0。固定720p的独立输出路径存在于硬件工程，不能仅凭上述1080输入侧配置就判定根因或盲写时序。
未重新加载位流、未写Flash或BOOT.bin。Windows窗口控制工具启动失败：permission path cannot be represented losslessly。现有JTAG程序未取得可用自动下载接口，因此未借GUI执行下载。
已请用户仅重启屏幕并重插HDMI（板子和Pluto不掉电），结果待回复。若仍黑，下一步检查HDMI线、屏幕输入及已验证合并位流的临时JTAG加载；先停止UI/接收再加载，加载后重新验证，不能宣称掉电持久化。

## 实际路径及运行差异

电脑：E:\\嵌赛\\rml24_stage7_execution_20261027
PC解包目录：pc/rml24_final_stage7_pc_selftest
板端包：/root/rml24_stage7_execution_20261027/rml24_final_stage7_board_overlay
板端新树：/root/rml24_stage7_execution_20261027/final
板端采集：/root/rml24_stage7_smoke_20261027、/root/rml24_stage7_formal_r1_20261027、/root/rml24_stage7_formal_r2_20261027

电脑网口仍192.168.126.50，板端192.168.126.49。尝试添加.10临时地址被Windows拒绝，未修改已有地址；使用两端已支持的listen-host/control-host参数显式设.50，未改包文件。TX枚举usb:1.8.5，RX枚举usb:1.3.5；下次需重新枚举，不能硬编码沿用。
板端默认base Python缺numpy，使用PATH显式选择/root/miniconda3/envs/torch_v2.0.1_aarch64/bin中的python3；没有修改系统Python。

## 关键产出

- formal_r1_score.json、formal_r2_score.json：固定240分母，含24类混淆矩阵、每类准确率和失败数。
- formal_r1_results.json、formal_r2_results.json：板端完整逐帧结果。
- formal_r1_tx、formal_r2_tx：电脑端收发记录与设备恢复。
- ui_build.log、ui.log、ui_r2.log、smoke.log、formal_r1.log、formal_r2.log：完整运行证据。
- final_board_evidence.txt：candidate/模型SHA、NPU纪律及恢复记录。
- raw_replay_audit.json、historical_archive_verify.json：历史回放与归档核验。
- historical_raw_tensor_captures.tar.gz：历史480份原始采集及candidate输入；SHA=5169956101f22a5bbd58c146eea790246de19618189b3c0d14f95db3a8e8701f。
- ui_same_tensor_audit.json：本次480帧星座/频谱/分类同源核验。
- framebuffer_snapshot.png：实际帧缓冲只读截图。
- STAGE7_EXECUTION_SUMMARY.json：机器可读结果。

## 复测入口

沿用包内BOARDTEST_STAGE7.md，采用全新run/out目录，电脑地址参数改为实际.50。板端运行run_final_receiver.sh前设置上述Python环境PATH。原恢复模块与模型保持冻结。
正式判分命令：python -I PC包/scripts/score_stage7_run.py --expected PC包/truth/expected_private.json --results 新结果.json --out 新判分.json。

范围仍为24类、自行生成RadioML张量兼容IQ、公开固定参考、双Pluto同轴固定参数；不证明无前导盲识别、空口、扫频或参数变化。触摸翻页、三页实物动态显示及重启自动显示尚未验收。
''';(r/'HANDOFF_STAGE7_EXECUTED.md').write_text(text,encoding='utf-8');print('REPORT_WRITTEN')