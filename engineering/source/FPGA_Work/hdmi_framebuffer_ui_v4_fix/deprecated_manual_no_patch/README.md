# deprecated_manual_no_patch/ — 已作废位流归档说明

> **目录用途**：记录 39e5 修复过程中被判定为**无效**的位流，统一标记
> **`REVOKED_DO_NOT_PROGRAM`**，严禁再加载到板上。

## 一、作废了什么

下列位流由 **`fpga/write_bitstream_manual.tcl`** 用 Vivado 直接执行
`write_bitstream -force` 生成。该方式**绕过了 Vivado run 管理器**，导致 FMSH 的
`write_bitstream_pre.tcl` / `write_bitstream_post.tcl` 钩子不触发，位流**没有打上
FMSH IP patch**，Procise 检测到 `IP Patch version: 0XFFFFFFFF`（正常应为 `53180205`）。

| 文件（已不再存在） | 大小 | IP Patch version | 作废原因 |
|---|---|---|---|
| `hdmi_framebuffer_720p_top.bit` | 5,980,037 B | `0XFFFFFFFF` | 缺 FMSH IP patch，绕过 run 管理器 |
| `hdmi_framebuffer_720p_top_disable_icap.bit` | 5,980,621 B | （由无 patch 的 .bit 生成） | 同上，继承缺 patch 问题 |

**状态：`REVOKED_DO_NOT_PROGRAM`。**

## 二、为什么这里没有实际文件

作废位流的**目标路径与新位流完全相同**（都写到
`fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/` 下的同名文件）。修正后的构建
（经 run 步骤脚本，正确应用 FMSH patch）**就地覆盖**了这两个文件，因此磁盘上
**已无旧位流残留**（已用 `find -size` 核实：旧尺寸 5980037 / 5980621 无任何残留）。

所以本目录**无法物理归档旧文件**，仅保留本说明 + 首次运行日志 `procise_1.log`
作为历史证据，如实记录作废原因。

## 三、证据

- 首次（无 patch）运行日志：`fpga/logfiles/procise_1.log`（记录 `IP Patch version: 0XFFFFFFFF`）。
- 修正后运行日志：`fpga/logfiles/procise.log`（记录 `IP Patch version: 53180205`）。

## 四、唯一有效位流（现在与以后）

| 用途 | 文件（绝对路径） | 大小 | SHA-256 |
|---|---|---|---|
| **上板（JTAG 临时加载，禁写 Flash）** | `F:/FPGA_Work/hdmi_framebuffer_ui_v4_fix/fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top_disable_icap.bit` | 5,980,619 B | `df8a0c669812835f7e6698ae0db0bb8524e6681bb211dfd1255bffe4ad1551b7` |
| 构建产物（不上板） | `.../hdmi_framebuffer_720p_top.bit` | 5,980,035 B | `9282f98ae785131e29f38ecb85762400fc2096cb2de604b7a4e4e094390eecd3` |

上板步骤见 `docs/BOARD_TEST_39E5.md`。
