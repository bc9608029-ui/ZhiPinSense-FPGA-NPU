# 本轮上板测试交接（2026-10-27）

状态：FIXED_REGRESSION_GATE_FAILED_SCAN_NOT_RUN_BASELINE_SERVICES_RESTORED

本轮尚未完成扫频验收。按 BOARDTEST_SCAN.md 的门禁，定频回归低于历史基线后暂停后续扫频和自启动切换。

## 已完成及结果

- 原部署包 SHA256：6bf4f2bb5577598ab4da8803a23e2c5df4a8037bee33af005dbc56f48ec06dbf。板端收到的包 SHA 一致，内部 27 文件校验全部通过。
- 独立副本的 7 个 prerequisite SHA 全部通过；没有强行跳过审计。
- 新四页 UI 在 aarch64 板端使用 -Wall -Wextra -Werror 原生编译 PASS。显示、帧缓冲和触控设备初始化日志正常，但没有请求用户实屏验收，不能宣称第四页实屏 PASS。
- 新双模式入口 FIXED 第1轮：237/240 = 98.75%。
- 新双模式入口 FIXED 第2轮：227/240 = 94.58%。
- 新入口合计：464/480 = 96.67%，低于历史 475/480 = 98.96%。这是相同240样本重复2次，不是480个独立样本。
- 为定位问题，原版 Stage7 TX + 原版 /opt/rml24-system 接收入口做完整对照：229/240 = 95.42%。旧链路当前也下降，尚不能将原因归于新扫频代码。
- 三轮均240帧、无缺帧、无恢复/推理失败；每轮 NPU 1920窗口，apply1/reset1919/discipline1；UI sent240/failed0；TX/RX恢复错误均0。
- 720个原始采集均保留板端。幅度只读检查：最大分量872、864、892，无分量接近2047的样点。只能说未见明显满量程削顶，不能据此确认RF链路完全正常。
- raw_quality.json 的 rx_readback 是所有测试结束、Radio.close恢复之后的设置，**不是测试期间设置**；不要将其中 slow_attack/30.72MS/s 误读成测试配置。测试入口明确调用 config_rx 设置manual35dB/2.56MS/s/18MHz/2.4GHz。

## 恢复与未执行项

新 UI 测试进程已停止；原 rml24-ui.service 和 rml24-receiver.service 已恢复，均enabled，UI active，接收服务保留原等待/重试逻辑。
原 /opt/rml24-system、systemd服务文件、SD启动位流、冻结模型和two-DC算法未改。新入口只在独立副本运行。

以下未执行，不可宣称PASS：偏频扫频240帧、宽范围扫频、失锁重扫、扫频无TX负对照、MODE页实屏与触控验收、新入口自启动替换及重启/冷启动。30–60分钟稳定性仍按用户指示不做。
历史定频475/480和原自启动验收证据仍是历史事实，但当前复测显示准确率波动，不能保证每次都达到98.96%。

## 路径

电脑证据：E:\scan_exec_20261027
板端独立目录：/root/rml24_scan_execution_20261027
板端待测试新程序：final/bin/board_ui_live_rml24_final、final/rml24_final/board_runtime/run_dualmode_receiver.sh
三轮原始采集与输入：fixed_r1/capture、fixed_r2/capture、legacy_control_r1/capture（均在板端独立目录内）
电脑 fixed_r*_results.json、fixed_r*_score.json、legacy_control_r1_results.json、legacy_control_r1_score.json 均为完整结果；private truth仅用于电脑判分，未传板。
board_evidence/ 为板端构建、UI、NPU、恢复及服务恢复日志的校验解包副本。
evidence_gate_failure.tar.gz SHA256：bae37dfcd6b3f6cf8efd35ff9b27fade443bb64486c32cb6ae6d44ad538954e1。

## 下一步

先定位当前原版链路为何无法稳定重现历史成绩（公共参考恢复诊断、原始IQ与恢复张量、SDR校准/链路条件的受控对照）。不要筛掉出错样本、修改真值或把现有95%左右写成99%。
重新建立可重复的定频基线后，再按原 BOARDTEST_SCAN.md 继续扫频门禁。若需改变验收门限或波形集合，先明确说明新口径，不能悄悄降低标准。