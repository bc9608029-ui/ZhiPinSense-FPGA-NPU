# 下一阶段顺序

1. 保留本包备份，确认板端现有模型、two-DC和工作位流SHA一致。
2. 明确恢复float IQ到特征int16旁路的固定转换、量纲与饱和规则；原模型float输入字节保持不变。
3. 基于现有官方BSP/整机工程，接入真实Power/Lag和Energy/Peak侧路，设计可回读的原始整数结果、帧ID/计数/版本/错误状态。不得臆造MMIO基址或把INT8张量当u32/s33结果。
4. 实现真实software/fpga/auto后端和驱动，软件保持默认；明确超时、帧号/长度/CRC/设备错误的回退行为。
5. 新整机工程先综合/P&R/完整STA，保留回退位流；先临时加载，不改开机默认。
6. 冻结19帧真板逐点零差异，再做同一真实恢复IQ的软件/FPGA A/B，验证统计、模型输入SHA和预测全等；做异常回退测试。
7. 定频240与两个扫频频点各240的RF回归；不能拿历史成绩代替新版本。独立验收集不得用于继续调参。
8. 补齐五页UI功能后板端构建和实屏触控；参数只显示已验证量，RMS按Energy派生，未经校准不能写dBm。
9. 满足门禁后才切systemd/启动位流，做新版本重启、冷启动及旧版本恢复。
10. 30–60分钟长稳定性仍暂缓，只有用户重新要求才执行。

主要数值/RTL证据：source/rtl、source/tb、source/vectors、source/tb/results、xsim_*.log、vector_comparison.json。
独立实现证据：procise_project、procise_qam、procise_qam_harness、procise_rtl。
默认禁止覆盖：/opt/rml24-system、现有SD启动文件、冻结BF16和two-DC。
