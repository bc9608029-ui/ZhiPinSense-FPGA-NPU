# 时钟 / 复位 / CDC 审计（任务 39e5 最终阶段 §四.9）

> 结论：两工程共用同一 200MHz 晶振根 + 同一 PS7 FCLK 树；NPU 额外有 MIG PL-DDR 时钟与
> SDI GTX 时钟。合并后的时钟域数量有限、均来自同一根晶振或 PS7，CDC 可沿用现有
> 同步器（level_cross/pulse_cross/async FIFO + ASYNC_REG 标签）。

## 1. 时钟树

```
200 MHz 晶振 (sys_clk_p/n, C8/C7)          PS7 FCLK_CLK0 (50 MHz)
  ├─ NPU 工程：                                              │
  │   ├─ MIG PL-DDR MMCM (ddr3 64-bit)                      └─ clk_wiz_0 → ps_clk_out = gp_clk (100 MHz)
  │   ├─ SDI GTX (148.5 MHz RXOUTCLK/TXOUTCLK, 156.25M refclk)
  │   └─ AI_CORE_CLK (PLLE2 @X1Y3, NPU 内核)
  └─ HDMI 工程：
      ├─ MMCM1: 200→27 MHz
      ├─ MMCM2: 27→74.25 MHz (像素) + 371.25 MHz (TMDS ×5)
      └─ MMCM3: 200→100 MHz (hp_clk, HP2_1 读时钟)
```

- 两工程都用 `PS7 FCLK_CLK0=50MHz → clk_wiz_0 → 100MHz gp_clk`（PS7 内 clk_wiz，同一 BD）。
- HDMI 的 hp_clk（100MHz）由 200MHz 晶振经 MMCM3 独立生成，与 gp_clk（PS7 PLL）**异步**。
- NPU 的 MIG/SDI/AI 时钟仅在 NPU 工程出现；HDMI 帧缓冲读用 PS DDR 经 `S_AXI_HP2_1`（hp_clk 域）。

## 2. 复位域

| 域 | 复位源 | 处理 |
|---|---|---|
| gp_clk（frame_ctrl/桥） | `sys_rst | soft_rst` | 双触发器同步（rst_gp_d1/d2） |
| hp_clk（fb_read_720p 读侧） | 同上 | 双触发器同步（rst_hp_d1/d2） |
| 74.25MHz 像素/cam 域 | `sys_rst | MMCM 未锁` | 移位寄存器 rst_sr，MMCM1+MMCM2 锁后再释放 |
| PS7 | `sys_rst_n & FCLK_RESET0_N` | ps_ai_wrapper 内 proc_sys_reset |
| NPU AI/MIG/SDI | NPU 工程各自复位 | 合并时需保留（若保留 SDI） |

## 3. CDC 边界（异步域交叉）

| 交叉 | 位置 | 既有同步 |
|---|---|---|
| gp_clk ↔ 像素/cam 域 | frame_ctrl | `bridge_s`/`level_cross`/`pulse_cross_camera` |
| hp_clk ↔ 像素域 | fb_read_720p | `level_cross` + async FIFO（afifo_16i_64o_largebuf / afifo_64i_16o_128） |
| 双缓冲选择位 | fb_read_720p | `buf_sel_sync1/2`（ASYNC_REG 标签） |
| 顶层复位 | top | 双触发器（ASYNC_REG 标签） |

HDMI 工程 XDC 已用 `set_clock_groups -asynchronous` 声明 hp_clk/74.25MHz/clk_wiz_0 三组异步，
并用 `ASYNC_REG` 标签覆盖全部同步触发器。NPU 工程 XDC 用 `set_false_path` 处理 GP↔cam、DDR↔cam、
clk_wiz 输出间交叉。

## 4. 合并后的 CDC 处理

1. 沿用 HDMI 工程的异步组声明 + ASYNC_REG 标签（覆盖帧缓冲读通路 + 复位）。
2. 保留 NPU 工程的 MIG/SDI/AI 时钟与 `set_false_path`（若**裁掉 SDI/cam**，则 SDI 相关约束一并删除）。
3. NPU 数据通路（AI_HP 512-bit CustomOp → MIG）与帧缓冲读通路（HP2_1）分属不同时钟/不同 DDR，天然隔离。
4. 新增唯一跨域点是：无（NPU 与帧缓冲读各自独立，无数据直接交互）。

## 5. 结论

时钟/复位/CDC 可合并，**无未处理 CDC 阻塞**。主要工作量是保留 NPU 时钟约束 + 沿用 HDMI 异步组，
并把可能裁掉的 SDI 时钟约束清理干净（避免悬空时钟告警）。见 §六硬门"无 unhandled CDC"。
