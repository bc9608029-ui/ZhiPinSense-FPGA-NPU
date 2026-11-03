# XFFT 9.1 width correction

真实 Vivado 2018.3 + FMSH ip_patch 5.3.1.8 生成结果冻结为：

- 输入：每路有符号 16 位；
- 变换：1024 点、fixed-point、unscaled、natural order；
- XFFT `C_OUTPUT_WIDTH=27`，不是早期预估的 26；
- AXI `M_AXIS_DATA_TDATA_WIDTH=64`，每路有效数据为有符号 27 位；
- `XK_INDEX=true`，`M_AXIS_DATA_TUSER_WIDTH=16`，低位承载索引；
- 完整输入域模平方最大值为 `2 * (-2^26)^2 = 2^53`，因此必须使用无符号 54 位；
- DDR/BRAM 传输字仍用 64 位，低 54 位有效，高 10 位必须清零。

旧的 26/52 位合同已作废。27/54 位合同已同步到 RTL、Python Golden、
XSim testbench、Procise OOC 外壳和板测文档。不得在适配器中静默截掉第 27 位。
