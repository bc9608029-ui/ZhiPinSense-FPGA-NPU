# 引脚 / XDC 冲突审计（任务 39e5 最终阶段 §四.10）

> 结论：**两工程引脚零冲突**（共用引脚完全一致）；真正的"冲突"不在引脚，而在
> **同一组 HDMI 引脚有两个驱动源**（NPU 的 SDI/cam 显示 vs HDMI 的 fb_read_720p），
> 合并时二选一即可。

## 1. 共用引脚对比（完全一致）

| 引脚 | 用途 | NPU 工程 XDC | HDMI 工程 XDC |
|---|---|---|---|
| AC17 | HDMI_CLK_P | `impl_constraints.xdc` | `hdmi_framebuffer_720p.xdc` |
| AA15 | HDMI_TX_P[0] | `impl_constraints.xdc` | 同 |
| Y16  | HDMI_TX_P[1] | `impl_constraints.xdc` | 同 |
| W16  | HDMI_TX_P[2] | `impl_constraints.xdc` | 同 |
| C8/C7 | sys_clk_p/n（200MHz） | `impl_constraints.xdc` | 同 |
| F8 | sys_rst（高有效） | `impl_constraints.xdc` / `ps_pl_ctrl_smoke_v2.xdc` | 同 |
| J1/M6 | led[0]/led[1] | `impl_constraints.xdc` | 同 |

HDMI 差分伙伴 `_N`（AC17/AA15/Y16/W16 的负端）在两边都只约束 `_P`、由 Vivado 自动配对，处理方式一致。

## 2. 各自独有引脚（互不重叠，无冲突）

| 引脚 | 所属工程 | 用途 |
|---|---|---|
| AB3/AB4, R6/R5 | NPU | FMC_HPC SDI（DP0_M2C / GBTCLK0_M2C 156.25MHz refclk） |
| E7 | NPU | `rx_gtx_full_reset` |
| AD16/AB14/AB15/AD15 | NPU | PJTAG（7030 Demo 调试口） |
| （无独有 I/O） | HDMI | HDMI 工程不新增独有 I/O（DDR/FIXED_IO 由 PS7 IP 自动约束） |

## 3. 时钟约束对比

- NPU `ai7030.xdc`：PLLE2 LOC（AI_CORE_CLK@X1Y3）、SDI GTX 4 时钟（6.734ns=148.5MHz）、
  若干 `set_false_path`（GP↔cam、DDR↔cam、clk_wiz 输出间）。
- HDMI `hdmi_framebuffer_720p.xdc`：`create_clock 5.000`（sys_clk）、`set_clock_groups -asynchronous`
  （hp_clk / 74.25MHz / clk_wiz_0 三组）、`ASYNC_REG` 标签、`set_false_path`（sys_rst/led）。
- 合并要点：HDMI 的异步组与 ASYNC_REG 标签需沿用；NPU 的 SDI GTX 时钟（若保留 SDI）需与 HDMI MMCM
  时钟并入异步组；若**裁掉 SDI/cam**（推荐，帧缓冲显示不需要 SDI），则 SDI 相关时钟约束整体删除。

## 4. 真正需要解决的"冲突"：HDMI 驱动源

- NPU 工程：`ps_ai_peripheral` 内部 SDI/cam → 显示通路 → 驱动 HDMI_CLK_P/N + HDMI_TX_P/N。
- HDMI 工程：`fb_read_720p`（帧缓冲读 + TMDS 编码）→ 驱动同一组 HDMI 引脚。
- 二者不能同时驱动同一物理引脚 → 合并必须**二选一**：停用/裁剪 NPU 显示通路，让 `fb_read_720p` 独占 HDMI。

## 5. 结论

- 引脚层：**无冲突**，共用引脚两工程取值一致，独有引脚互不重叠。
- 驱动层：HDMI 引脚二选一（用 fb_read_720p），这是合并方案的第 2 步，属 RTL 集成而非 XDC 冲突。
