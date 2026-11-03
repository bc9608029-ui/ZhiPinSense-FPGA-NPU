# Build Round 01 — 合并位流综合（smoke_v1 第 1 步）

时间：2026-10-06
工程基座：`fpga/npu_base/fpai_demo_vivado.xpr`（NPU 基座拷贝，Part=xc7z030ffg676-2）

## 本轮修改内容
1. 新增 `fpga/npu_base/rtl/display/fb_read_720p.sv`（720p 帧缓冲读取链路，拷贝自 HDMI 工程）。
2. 新增 `fpga/npu_base/rtl/ps_ai_peripheral_combined.sv`：
   - 模块改名 `ps_ai_peripheral` → `ps_ai_peripheral_combined`；
   - 新增 `input clk_371m25`；
   - 用 `fb_read_720p` 替换官方 `frame_to_ps_largebuf`（HP2_1 主接口从"写采集帧"改为"读帧缓冲"）；
   - 删除 `assign S_AXI_HP2_WID = 6'h00;`（改由 fb_read_720p 驱动 5bit WID）。
3. 新增 `fpga/pl_ddr_integration_v1/rtl/pl_ddr_mandatory_core_top_combined.sv`：
   - 模块改名 + 实例 `ps_ai_peripheral_combined`；
   - 插入 HDMI 时钟链：IBUFDS(200M) → MMCM1(200→27M) → MMCM2(27→74.25M+371.25M) → BUFG；
   - `.cam_clk(hp_clk)` → `.cam_clk(clk_74m25_bufg)`，新增 `.clk_371m25(clk_371m25_bufg)`；
   - `clk_wiz_core_50` + `pl_ddr_mandatory_core_engine` 不变。
4. 已替换（此前轮次）：`display/aq_axi_master.v`（39e5 半字反转修复版）、`display/video_define.v`（720p）。

## 为什么必须重跑 PnR
首次合并构建：新顶层模块 + 新增 fb_read_720p 实例 + 新增 MMCM1/MMCM2 时钟链，
与原基线位流无共享 checkpoint。

## 使用的 checkpoint
无（全新构建）。

## 输入 SHA256（本轮关键文件）
- fb_read_720p.sv                    5f1c8ac860c410d8d6d4bf5ef45f61b8c159f6964855baad72788b85f710aac8
- aq_axi_master.v（39e5 修复版）       5a181a799afc5c469a908f7416ee637824941ef5f15aea0978d50cceac485246
- video_define.v（720p）              b7582475f29668b66d27ca00d681e7814ef0e463dfd9dbf1905d646b96fb8b3c
- ps_ai_peripheral_combined.sv        a675a75e941257978782481022f118596d5899942d285da29e0baddf167f0778
- pl_ddr_mandatory_core_top_combined.sv f8df7875aeacf8ae59d44340a4ba74b947907a8f81925744d372379f75831410
- m3_synth_combined.tcl               11cf324c4f19821a2a860ac36fac7930389e7e9866d8be9eb21d982d17b3654a

## 顶层 XDC SHA256
- ps_pl_ctrl_smoke_v2.xdc  f30d1ca14127aa4309365071bdc04733a4b3f7ca89fe803ce39f1c42f9b5aa85
- impl_constraints.xdc     7ca36176517418511de6c34fab93a1fdfe787bf3bb560b31143988881193696f
- ai7030.xdc               6fd7b68da8e4e9ae30ca9a868ad38ca43a1d1ab44e3b23435cdf072fbc4b29d9

## 磁盘（构建前）
C: 37G free (86% used)；F: 852G free (11% used)。均高于门限（C≥10G, F≥30G）。

## 并行度
-jobs 4（符合 2~4 限制）。

## 结果
（待综合完成回填）
