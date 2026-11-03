# 验证状态

- Python Golden/向量/检测/位宽反例：已执行并PASS。
- 新RTL边界testbench：已准备。
- 本机未找到Icarus、Verilator、xsim或Procise命令行工具，因此新RTL仿真标记SKIPPED，不冒充PASS。
- 既有Power/Lag RTL的历史验证不能替代本次FFT智能扫频RTL验证。
- 下一步先行为仿真，再Procise独立综合/P&R/STA，最后板端同帧A/B。
