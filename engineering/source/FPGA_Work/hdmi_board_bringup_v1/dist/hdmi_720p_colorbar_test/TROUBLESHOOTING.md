# TROUBLESHOOTING —— HDMI 720p 色条上板排错

按**现象**查表。先看 LED，再看屏幕，再看链路。

## 现象 → 排查表

| 现象 | 最可能原因 | 处置 |
|---|---|---|
| `led[0]` 不亮 | 两级 MMCM 未锁定：输入 200MHz 没进、MMCM 参数错、复位被拉死 | 检查 12V/SW8 已上电；查 `clock_report`；量 C8/C7 是否有时钟 |
| `led[0]` 亮、`led[1]` 不闪 | 像素时钟 74.25MHz 未到 BUFG / 后续逻辑被复位卡住 | 查 `timing_summary` 是否 WNS<0；复位极性是否被误接 |
| 屏幕 **无信号/黑屏** | ①HDMI 线/显示器问题 ②未加载成功 ③TMDS 无输出 ④74.25MHz 不对 | 先复测 PC 接同一显示器；再确认 Program "completed successfully"；查 HDMI 引脚 XDC |
| 屏幕有画面但**闪烁/撕裂** | TMDS 5× 时钟 371.25MHz 或像素时钟抖动；1080p 误配 | 确认是 720p（本设计固定 720p）；查 `timing_summary` 中 371.25MHz 路径 |
| **颜色顺序错 / 缺色 / 只有黑白** | RGB 位线错接或 TMDS 数据 lane 错序 | 对照官方 XDC：`AC17=CLK_P`、`AA15/Y16/W16=TX_P[0..2]` |
| **只有部分颜色 / 花屏** | OSERDESE2 10:1 串化时钟相位错；371.25MHz 与 74.25MHz 相位不对 | 这是时钟域问题，先看 `clock_report` 两时钟是否同源同相；必要时换 BUFIO 走 5× |
| 加载后 **几秒掉配置** | PS 经 PCAP/ICAP 重新配置了 PL（未用 disable_icap 位流） | 确认加载的是 `_disable_icap.bit`（不是裸 `.bit`） |
| Program 报 **device not found / no target** | JTAG 线接错口（接了 U18 或 PS UART）、下载器驱动、SW8 没上电 | 确认用 **PL JTAG=U19**；重新 Auto Connect；检查下载器驱动 |
| 出现 **多个器件** 不知选谁 | 级联 JTAG 链 | 选 PL 器件 `xc7z030_0`，不要选 ARM DAP / PS 器件 |
| 闻到**焦味/发烫/异常电流** | 硬件问题 | **立即断电**，停止一切，报告硬件异常 |

## 时钟核对（关键）

本设计两级 MMCM，期望频率：

| 时钟 | 期望 | 来源 |
|---|---|---|
| `clk_200m` | 200 MHz | 板上晶振 C8/C7（`DIFF_SSTL15`） |
| `clk_27m` | 27 MHz | MMCM1 `200*27/5=1080 → /40` |
| `clk_74m25_bufg` | 74.25 MHz | MMCM2 `27*55/2=742.5 → /10` |
| `clk_371m25_bufg` | 371.25 MHz | MMCM2 `742.5 → /2` |

若 `clock_report` 里任一频率偏差超过约 0.1%，先查 MMCM 参数，不要盲目上板。

## 时序核对

本包 `timing_summary` 应满足 **WNS ≥ 0 且 WHS ≥ 0**（setup/hold 均无违例）。若你手头
这份为负，**不要上板**，先回到构建环节修复时钟/约束。

## DRC 核对

本包 `DRC_report` 应 **无 Error**。Warning 若涉及关键约束（时钟/HDMI 引脚）需逐条核对，
不得通过降低 DRC 严重级别或删约束的方式"通过"。

## 复位核对

`sys_rst`(F8) 为**高有效**（官方 `demo_clkrst_wrapper.v` 用 `sys_rst|soft_rst`，官方
`color_bar.v` 注释 "reset signal high active"）。本设计 `rst = sys_rst | 未锁定位`，锁
定后自动释放；即使不按复位键也应能出画面。

## 快速二分法

1. **先排除显示链路**：PC 接同一显示器/线 → 能出 720p60？不能则显示器/线问题。
2. **再确认加载成功**：Program 报 "completed successfully" 且 `led[0]` 亮。
3. **再看 TMDS**：`led[0]` 亮但屏幕无信号 → 查 HDMI XDC 引脚 / 时钟 / 5× 串化。
4. **最后看稳定**：有画面但闪 → 查 371.25MHz 路径时序 / 换 BUFIO。

> 每一级失败都按 `BOARD_TEST_GUIDE.md` E 节收集完整信息后再求助，不要只报"黑屏"两个字。
