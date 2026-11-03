# 任务7：能否通过官方 wrapper/IP 配置关闭 1 GHz NPU 计算时钟 —— 只读结论

**结论：不能。** 在不动 EDIF、不新建门控逻辑、不影响 User_Ddr_* 的前提下，1 GHz `clk_out1_AI_CORE_CLK_ST_1` 无法被关闭。证据如下（全部只读追踪 AI_Mate.edif，未做任何修改）。

## 时钟结构（`u_AI_Mate_top/clkrst_wrapper_u0/AI_CORE_CLK`）

EDIF `rtl/edif/AI_Mate.edif:405242` 起的 clk_wiz 单元 `AI_CORE_CLK_ST_AI_CORE_CLK_ST_clk_wiz` 内含：

| 对象 | 连接 | 含义 |
|---|---|---|
| `plle2_adv_inst` PWRDWN | `G`（GND，const0） | **PLL 永不掉电**，无电源门控 |
| 动态重配 DADDR[6:0]/DCLK/DEN/DWE/DI[15:0] | 全部 const0 | **运行期重配频率被硬件禁用**，无法软件降频 |
| `reset` 端口 | `u_AI_Mate_top/sys_rst` | PLL 复位 = NPU 全局复位 |
| CLKOUT0 | `clkout1_buf`（BUFG）→ 1 GHz | 唯一输出，直入 BUFG |

## 复位链路（reset 不可独立控制）

```
sys_rst_n (NPU 顶层复位输入端口, 来自 PS/板级, 低有效)
   └─ AI_CORE_CLK_i_1 (LUT1, INIT=2'h1, 反相器)  →  sys_rst (高有效)
        └─ clk_wiz reset → PLLE2_ADV RST
        └─ u_sync_ai_rst / u_sync_ddr_clk_rst / u_sync_gp0_clk_rst / u_sync_hp0_clk_rst / u_sync_ui_clk_rst
        └─ rst_d1/d2/d5/d6_*_reg（各时钟域复位同步链）
```

即：PLL 的 `reset` 与 **整个 NPU 的系统复位 `sys_rst` 共用同一根网**。要"关掉 1 GHz"，唯一路径是拉高 `sys_rst`（或拉低 `sys_rst_n`），但这会：
1. 复位整个 NPU（ai/ddr/gp0/hp0/ui 五个时钟域全部复位）—— NPU 完全停摆，失去集成意义；
2. 连带复位 NPU 的 DDR 接口 `ddr_intf_u` / `U0_ddr2hp_itcn`（即 User_Ddr_* 数据通路）—— **影响 User_Ddr_***。

## 三条可能的"关闭"路径逐一排除

| 路径 | 可行性 | 原因 |
|---|---|---|
| PLL 掉电（PWRDWN） | ❌ | PWRDWN 在 EDIF 内硬接 GND，无外部端口 |
| 动态重配降频/关闭 | ❌ | DADDR/DCLK/DEN/DWE/DI 全部硬接 const0，且 clk_wiz 无外部重配端口 |
| 拉复位（reset） | ❌ | 与 NPU 全局复位 `sys_rst` 共用，会复位整个 NPU 并影响 User_Ddr_* |

## 补充事实

- 1 GHz 时钟当前**仅驱动 1 个寄存器** `ai_core_clk_locked_reg`（锁存 PLL locked 状态），NPU 实际计算逻辑跑在 `clk_pll_i_1`（200 MHz，来自 MIG 基础设施 MMCM，驱动 16444 个 FD）。即该 1 GHz 在本次集成中**无实际计算负载**。
- 该 PLL（`PLLE2_ADV_X1Y3`）是官方 AI 核内部固化结构，任何"选择性门控 1 GHz 而保留 NPU"的做法都必须：改 `AI_Mate.edif`（被明令禁止）或在 vendor IP 边界外新增门控/约束（同样属于改冻结 IP）。

## 对 P0 的含义

1 GHz BUFG Min-Period（-0.409 ns）是**官方 NPU 固有时钟结构的确定性结果**，约束级/配置级均无法消除。因此它与「官方是否接受该违例并出位流」一并，仍归结为 **唯一 P0：需 FMSH FAE 书面确认**（官方 timing summary / 内部 waiver / 推荐频率）。不 waive、不降频、不改 EDIF、不生成 bitstream。
