# 本轮产出入口

先读 HANDOFF_SCAN_AUTOTEST.md；机器可读结果是 FINAL_SCAN_AUTOTEST_SUMMARY.json。

本轮居中候选V2在两个频点各236/240，合计472/480（相同240波形重复，不是480个新样本）。跳频与静默验证、四页实屏已完成。原定频波动尚未解决，新版本未切开机默认，未做新版本冷启动或长稳定性。

- candidate_v2_fourpage_waterfall_tree.tar.gz：板端候选源码及原生程序；需要现有冻结模型和legacy依赖，非完整系统镜像。
- board_runtime_evidence.tar.gz：构建、NPU、恢复、触控与恢复原服务的板端日志。
- *_results.json / *_score.json / *_audit.json：逐帧结果、固定分母判分与专项审计。
- PHYSICAL_UI_CONFIRMATION.json：用户实屏确认。
- REPRODUCE_CANDIDATE.md：已有设备上的复现路径与命令。
- HANDOFF_SCAN_BOARDTEST.md：此前定频门未通过时的阶段记录；后续状态以总交接说明为准。

最终ZIP是电脑证据包，含电脑侧私有判分材料，不能整体传板。只传单独审计过的板端候选树。
所有原始RF采集和输入张量仍保留在板端 /root/rml24_scan_execution_20261027/<run>/capture/。