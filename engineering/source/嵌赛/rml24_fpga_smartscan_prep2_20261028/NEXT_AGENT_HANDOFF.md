# 唯一交接入口

依次阅读：

1. `docs/HANDOFF_FPGA_SMART_SCAN_PREP2.md`
2. `docs/VERIFICATION_STATUS.md`
3. `docs/BOARDTEST_SMART_SCAN.md`

先运行两个 Python 自检和 `scripts/hdl_sim.ps1`。当前 Golden/RTL 仿真、Vivado XFFT 9.1
生成综合及不含 FFT 的 Procise 后级 OOC 实现已完成。下一步是完整 XFFT 迁移集成、PS/PL
通路和自动回退；尚无完整候选位流，未上板。
