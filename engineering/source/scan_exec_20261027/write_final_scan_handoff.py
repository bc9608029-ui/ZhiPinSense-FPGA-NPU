import pathlib,json,hashlib
p=pathlib.Path(__file__).parent
load=lambda n:json.loads((p/n).read_text(encoding='utf-8'))
fixed=[load('fixed_r1_score.json'),load('fixed_r2_score.json')];old=load('legacy_control_r1_score.json');orig=[load('scan_narrow_r1_score.json'),load('scan_wide_r1_score.json')];cand=[load('centered_narrow_v2_score.json'),load('centered_wide_v2_score.json')];challenge=load('challenge78_v2_audit.json');ui=load('PHYSICAL_UI_CONFIRMATION.json');replay=load('historical_npu_replay_audit.json');ctl=load('mode_control_audit.json')
summary={'date':'2026-10-27','status':'SCAN_CANDIDATE_RF_UI_TESTED_FIXED_ACCURACY_GAP_REMAINS_BOOT_UNCHANGED','fixed_accuracy_issue_resolved':False,'historical_fixed_correct':475,'historical_fixed_total':480,'current_fixed_correct':sum(x['correct'] for x in fixed),'current_fixed_total':480,'legacy_control_correct':old['correct'],'legacy_control_total':240,'original_scan_correct':sum(x['correct'] for x in orig),'original_scan_total':480,'candidate_scan_correct':sum(x['correct'] for x in cand),'candidate_scan_total':480,'candidate_same_240_waveforms_at_two_frequencies':True,'candidate_challenge':challenge,'historical_npu_exact_replay':replay,'mode_control':ctl,'physical_ui':ui,'new_systemd_entry_installed':False,'new_runtime_reboot_or_cold_boot_tested':False,'long_stability_tested':False,'note':'All modified-candidate evaluations are development comparisons on reused waveforms; not independent generalization accuracy.'}
(p/'FINAL_SCAN_AUTOTEST_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
rows=[('历史定频（历史事实）',475,480),('本次新入口 FIXED 两轮',sum(x['correct'] for x in fixed),480),('本次原版对照',old['correct'],240),('原扫频：2401.3 MHz',orig[0]['correct'],240),('原扫频：2397.4 MHz',orig[1]['correct'],240),('居中候选V2：2401.3 MHz',cand[0]['correct'],240),('居中候选V2：2397.4 MHz',cand[1]['correct'],240)]
table='\n'.join(f'| {label} | {a}/{b} | {a/b*100:.2f}% |' for label,a,b in rows)
text=f'''# 扫频上板测试与准确率排查：交接入口（2026-10-27）

状态：`{summary['status']}`。

原定频波动尚未解决；独立扫描居中候选在两个频点的完整开发对照改善到 {summary['candidate_scan_correct']}/480（{summary['candidate_scan_correct']/480*100:.2f}%）。新四页UI已经用户实屏确认。未替换原开机入口，不宣称新版本已经冷启动或稳定性通过。

## 结果口径

| 测试 | 正确数/分母 | 准确率 |
|---|---:|---:|
{table}

480是相同240个波形在两轮或两个频点重复，不是480个独立波形。候选已使用这些结果调试，所以是开发对照，不能包装成新的独立泛化成绩。
所有正式分母240固定，缺帧/无效均算错。PC私有真值只在电脑判分，未发板。跳频计划只在电脑控制真实TX LO，不传给RX。

## 已找到和修复的范围

1. 模型与NPU：历史240个输入张量重新送入同一真实NPU，输入SHA、预测和平均logits全相同，最大logit差0。该证据支持这组输入的推理端未改变。
2. 当前原版也只有229/240，因此不能把定频波动归咎于扫频代码。少量波形诊断显示当前恢复误差略大，尚无已验证的定频根因修复。不要重训或改模型来掩盖该事实。
3. 原扫描锁在网格LO后数字校频，会改变冻结two-DC面对的直流基底条件。V2候选改为用公共训练段估计真实信号中心，调谐真实RX LO、读回和刷新，再把未预旋转IQ送入原two-DC。
4. V2新增居中锁频的一致性界限1000Hz；原公共训练分数门限0.10保留。复核失败会保留为无效帧并解锁，而不直接中断整轮协议。FIXED分支AST与原版一致，冻结two-DC和BF16模型不改。
5. 第一版居中候选在完成46帧后失败，中断证据保留。其固定240分母记录45/240，缺194帧，不能称45/46通过或删除这轮。
6. 新四页增量漏带已验证瀑布修复；本轮补回真实谱历史、生产者重连清空和正确int16转换，仅改显示。原生产目录未覆盖。

## 功能与实屏

- 原版跳频：2397.4→2403.6→2397.4MHz，两次丢锁后重扫均成功。72信号帧68正确，6静默帧均未输出类别，但一次公共发现误命中后被two-DC拒绝。必须保留前级误触发缺口。
- V2同一计划：信号 {challenge['signal_correct']}/72；缺帧 {len(challenge['signal_missing'])}，无效 {len(challenge['signal_invalid'])}。静默最终拒绝 {challenge['end_to_end_muted_rejections']}/6，错误类别 {challenge['false_muted_classifications']}，前级误命中 {len(challenge['public_discovery_false_hits'])}。具体见 challenge78_v2_audit.json。
- 独立24帧控制：STOP允许一帧在途完成，随后计数保持不变；START继续；FIXED/BAND_SCAN实际出现在RF记录；AUTO_LOCK返回unsupported_mode。ACK只表示控制状态更新，不能单凭ACK证明LO瞬时完成。
- 用户已确认四标签和MODE导航，模式切换/暂停/恢复，以及频谱、瀑布、星座更新。实际触控日志6命令、6applied、无拒绝/超时/重复。
- 星座为恢复后IQ采样散点，未做符号定时。18个右上角占比≥98%的记录中17个真值AM-SSB-WC、1个8ASK，坐标映射保留正负号。不能把所有右上角点云都视为错误，也不能用图形美观替代判分。

## 禁止误报

原定频98.96%是历史成绩，当前464/480是新的下降事实。候选扫码改善不等于原定频问题已解决。未做长稳定性、空口/干扰/变采样率/任意外部无前导盲识别。AUTO_LOCK未实现。新版本未切systemd或做重启/冷启动验收；旧版本历史启动验收不能自动挪给新版本。

## 文件与复现位置

电脑证据根：`E:\\scan_exec_20261027`。
板端根：`/root/rml24_scan_execution_20261027`。

- 原准备包：`E:\\嵌赛\\rml24_scan_final_prep1_20261027\\dist\\rml24_scan_final_prep1_pc_ready.tar.gz`，SHA256 6bf4f2bb5577598ab4da8803a23e2c5df4a8037bee33af005dbc56f48ec06dbf。
- 冻结Stage7生产树：`/opt/rml24-system`；冻结依赖 `/root/amr_rescue_20261025`；模型 `/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16`。
- 原增量副本：`final/rml24_final/board_runtime/run_dualmode_receiver.sh`。
- V2候选：`final/rml24_final/board_runtime/run_centered_v2.sh` 与 `rml24_dualmode_receiver_centered_v2.py`。绝不覆盖原脚本。
- 四页瀑布源树/原生二进制：`ui_fourpage_waterfall/`，相对板端根；实际binary为 `bin/board_ui_live_rml24_final`。
- 所有每轮目录的 `capture/` 保留原始.npy、输入.bin、results.json和ui_events.jsonl；UI长演示r2刻意没有保存大体积原始样本，只用于操作确认，不作准确率成绩。
- 电脑 `*_results.json`、`*_score.json`、`*_audit.json` 为复制校验/判分证据。`historical_npu_replay_audit.json`、`PHYSICAL_UI_CONFIRMATION.json`、`mode_control_protocol.json` 为专项证据。
- 完整审计汇总：`FINAL_SCAN_AUTOTEST_SUMMARY.json`。
- 后续若传部署包，只传板端树或明确白名单增量，不能把包含私有truth/schedule的电脑证据包整体传板。

## 下一步

先明确比赛能接受的准确率与受控公共帧边界；若要正式部署新版本，仍需在独立新波形/采集上验证候选、解决或明确接受定频回归缺口，再切换服务并完成新版本重启/冷启动验收。长稳定性仍按用户要求暂不做。不要悄悄降低门限、删除错误样本或替换历史基线。
'''
(p/'HANDOFF_SCAN_AUTOTEST.md').write_text(text,encoding='utf-8')
print('FINAL_HANDOFF_WRITTEN',summary['status'])