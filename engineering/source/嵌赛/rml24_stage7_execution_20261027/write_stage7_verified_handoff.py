from pathlib import Path
import json,hashlib,tarfile
r=Path(r'E:\嵌赛\rml24_stage7_execution_20261027');a=json.loads((r/'waterfall_fix1_r1_score.json').read_text(encoding='utf-8'));b=json.loads((r/'waterfall_fix1_r2_score.json').read_text(encoding='utf-8'));ui=json.loads((r/'waterfall_fix1_same_tensor_audit.json').read_text(encoding='utf-8'));assert ui['passed']==ui['total']==480
archive=r/'stage7_waterfall_fix1_board_tree.tar.gz';assert hashlib.sha256(archive.read_bytes()).hexdigest()=='beac8e07f661e1e4dcdea74c9ad5fd4324cfb72ea4dcc25667b0675e42023062'
with tarfile.open(archive,'r:gz') as t:
 names=t.getnames();assert not any('/truth/' in n or 'expected_private' in n or 'selftest_manifest' in n or '/dataset/' in n for n in names)
 checks={'final_waterfall_fix1/bin/board_ui_live_rml24_final':'3950201f64f4575755840df2d98879b5d3e44a109372192366d67a90652adaf6','final_waterfall_fix1/rml24_final/recovery/candidate_two_dc.py':'e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a'}
 for n,h in checks.items():assert hashlib.sha256(t.extractfile(n).read()).hexdigest()==h,n
summary=dict(status='STAGE7_RUNTIME_RF_HDMI_VERIFIED_BOOT_PENDING',final_board_root='/root/rml24_stage7_execution_20261027/final_waterfall_fix1',final_runs=[{k:s[k] for k in ('correct','total','accuracy','failure_count','missing_sequences')} for s in (a,b)],correct=a['correct']+b['correct'],total=480,accuracy=(a['correct']+b['correct'])/480,historical_independent_validation_correct=463,historical_independent_validation_total=480,final_retest_is_new_independent_dataset=False,hdmi_physical='User-confirmed classify/spectrum-waterfall/constellation photos saved',model_changed=False,recovery_changed=False,ui_only_changed_files=['board_package/board_ui_live_rml24_final.cpp','board_package/unix_socket_server.hpp'],ui_process_checks=json.loads((r/'waterfall_fix1_process_test.json').read_text()),ui_same_tensor=dict(passed=480,total=480),no_tx_probe=json.loads((r/'no_tx_probe_result.json').read_text()),boot_persistence='NOT_IMPLEMENTED; temporary Program FPGA only',pending=['>=30 minute continuous stability test','persistent known-bit boot path and automatic app startup','cold power-cycle acceptance after persistence implemented'],board_package_sha256='beac8e07f661e1e4dcdea74c9ad5fd4324cfb72ea4dcc25667b0675e42023062');(r/'STAGE7_FINAL_VERIFIED_SUMMARY.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
text='''# Stage7 最新唯一交接入口（2026-10-27）

状态：STAGE7_RUNTIME_RF_HDMI_VERIFIED_BOOT_PENDING。

先读本文件。旧 HANDOFF_STAGE7.md 是上板前准备入口；HANDOFF_STAGE7_EXECUTED.md 保留排查过程，其中早期黑屏/瀑布缺失状态已被本文件取代。当前尚未完成掉电保留、自动启动和长时间稳定性验证，不得宣称PROJECT_COMPLETE。

## 当前已经实机验证

1. 用户临时Program FPGA加载给定合并位流后，新UI由重复错位恢复为正常单份界面。用户确认这次是加载.bit，不是Program Flash。
2. 原Stage7 UI有实际集成遗漏：频谱页调用render_parameters时未提供WaterfallHistory，因此虽然谱数据有效仍显示旧参数布局。修复只改2个UI文件，独立树保留旧版本可回退。
3. 新UI接入真实256-bin谱历史，最大128行、10Hz上限，新生产者连接清空历史；分类、相对频谱/瀑布、256点恢复IQ星座均已在实物屏幕确认，照片保存。
4. aarch64原生UI构建成功。真实headless UI进程6项检查全通过：正常退出、两次连接清空、每连接首行、历史推进、重复帧去重、畸形谱拒收。首次类型不匹配构建失败日志保留，修正后最终二进制已实测，不以旧失败产物冒充成功。
5. 最终修复版完整收发第一轮237/240=98.75%，停止重启UI/NPU/TX/RX后第二轮238/240=99.17%，合计475/480=98.96%。均无缺帧、恢复/推理失败、设备恢复错误，UI每轮收齐240条且拒收0。
6. 每轮真实NPU1920窗口，apply1/reset1919/discipline1；模型和恢复器SHA未变，没有调参、改变帧结构或删样本。
7. 最终480帧显示同源审计通过：保存的NPU输入SHA、分类与UI事件一致，重新计算星座与谱值相同。历史480份raw到tensor逐字节回放也全部通过且已复制回电脑。
8. 发射端测试程序关闭后，另做3次真实RX噪声采集，均因无可用公共前导被拒绝，未调用NPU、无预测类别、设备恢复无错误。该独立负样本检查不计入240分母。失败UI适配器当前不发分类，界面随超时STALE；不能宣称已有完整实时NO_SIGNAL/热拔插恢复产品流程。

## 准确率口径

- 463/480=96.46%是此前冻结候选的历史独立验证。
- 475/480=98.96%是本次最终UI集成复测，使用同一组240个不同样本重复收发两轮，不是480个不同样本，也不是新的独立数据集泛化证明。
- 本轮没有利用结果调整模型、恢复算法或门限。星座为恢复IQ采样散点，不是完成符号同步后的判决星座。
- 范围仍为公开固定前后参考、双Pluto同轴、2.4GHz、2.56MS/s、18MHz、TX -40dB、RX手动35dB、载荷1024重复8次。不能外推无前导、空口、扫频、可变符号率或低SNR。

## 当前有效部署与路径

PC执行根：E:\\嵌赛\\rml24_stage7_execution_20261027
板端最终树：/root/rml24_stage7_execution_20261027/final_waterfall_fix1
最终UI：上述树/bin/board_ui_live_rml24_final
旧树：/root/rml24_stage7_execution_20261027/final（没有瀑布接入，不要误用为最终版）

最终完整板端树包：stage7_waterfall_fix1_board_tree.tar.gz
SHA256：beac8e07f661e1e4dcdea74c9ad5fd4324cfb72ea4dcc25667b0675e42023062
包含源码及已在aarch64运行的UI二进制，已独立读包核验二进制/恢复器SHA，未包含truth、expected_private、selftest_manifest或dataset路径。依赖的legacy runtime和冻结模型仍位于原板端外部目录，不能误称完全自包含系统镜像。
UI二进制SHA：3950201f64f4575755840df2d98879b5d3e44a109372192366d67a90652adaf6
UI源码SHA：fa2be96b287e20d16be2d7f0d60d73d20d95218561c3cbfaf3331a04395056ac
socket头SHA：2a2d0f9966c1926c3c8686b692177cf0b2ddf9f7662fe7108ff14f44c5aa26fd

PC测试包沿用原rml24_final_stage7_pc_selftest.tar.gz，SHA e23cf53c249f8b2c17611a8047fc0b583fc92be51a17b57359138a14362c61a3。
解包目录：执行根/pc/rml24_final_stage7_pc_selftest。真值只留电脑。

恢复器SHA：e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a
模型JSON SHA：28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42
模型raw SHA：c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151
模型目录：/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16
legacy根：/root/amr_rescue_20261025
Python环境：/root/miniconda3/envs/torch_v2.0.1_aarch64/bin（默认base python3没有numpy）

PC网口192.168.126.50，板子192.168.126.49。原交接默认.10未使用，因为Windows不允许加地址；两端通过已有参数显式使用.50，算法未变。最新TX USB URI为usb:1.8.5，RX为usb:1.3.5，下次必须重新枚举。

## 启动及复测

先确认已加载正确位流（仅软件版本门不能代替掉电持久化验收）。提供的位流E:\\tmp\\stage7_combined_hdmi.bit，SHA22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9。
先启动最终UI：

```bash
/root/rml24_stage7_execution_20261027/final_waterfall_fix1/bin/board_ui_live_rml24_final --sock=/run/sdr_amr_ui_rml24_final.sock --ctl-sock=/run/sdr_amr_control_rml24_final.sock --display-refresh-hz=30
```

再在电脑启动PC包pc_runtime/rml24_final_tx.py，使用-I、--legacy-root E:\\AMR_Rescue_20261025、--dataset PC包/dataset、--manifest PC包/pc_runtime/selftest_manifest_240.json、--out全新目录、--listen-host192.168.126.50。
然后板端设置PATH选择上述Python，使用最终树/rml24_final/board_runtime/run_final_receiver.sh --run全新目录 --legacy-root上述legacy根 --model-dir上述模型根 --control-host192.168.126.50 --save。
UI_SOCKET=/run/sdr_amr_ui_rml24_final.sock。不要并行启动多个NPU模型。
按PC包scripts/score_stage7_run.py判分，固定240分母，缺失和失败均计错。

## 证据

waterfall_fix1_r1_score.json、waterfall_fix1_r2_score.json含混淆矩阵和每类准确率；对应results.json、TX目录、日志均在执行根。
waterfall_fix1_process_test.json/log为6项真实进程测试。
waterfall_fix1_same_tensor_audit.json为最终480帧同源核验。
no_tx_probe_result.json为3次真实无发射检查。
waterfall_fix1_final_board_evidence.txt为模型/恢复SHA、NPU纪律、恢复与进程检查。
physical_waterfall_confirmed.jpg、physical_constellation_confirmed.jpg为用户实物照片。
板端最终原始采集在/root/rml24_stage7_waterfall_fix1_r1_20261027/capture与r2同名目录。
最终captures归档waterfall_fix1_final_captures.tar.gz由后台生成，须确认完成后取回比对SHA；不能把未完成文件当完整证据。

## 未完成，后续优先级

1. 至少30分钟的持续收发稳定性测试（不是单纯UI空闲驻留）。
2. 系统层面USB/网络断连与恢复流程；现有UI已验证生产者socket重连，但不等同于USB热插拔通过。
3. 依据已验证位流、启动介质和厂商流程实现上电加载及应用自动启动；写介质前先备份当前启动内容。现在仅做过只读启动环境采集，未写Flash/BOOT.bin。
4. 完成后再做真正断电重启、无需电脑JTAG的整机验收。当前不能宣称独立上电演示已经完成。
''';(r/'NEXT_AGENT_HANDOFF_STAGE7_VERIFIED.md').write_text(text,encoding='utf-8');print('FINAL_REPORT_PASS',summary['correct'],summary['total'])