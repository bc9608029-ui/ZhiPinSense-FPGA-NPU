# Phase 1 — M1 基线复现 + M2 frame_ctrl 接入（任务 39e5 最终阶段）

> 本回合交付边界：**只做 M1 + M2 + 1GHz 时序决定性分析**（见 `TIMING_1GHZ_DECISIVE_ANALYSIS.md`），
> 回报后再继续 M3-M7。不产出最终合并位流，不标硬件 PASS。

---

## 0. 环境就绪核查（M1 前置，已完成）

| 项 | 状态 | 证据 |
|---|---|---|
| Vivado 2018.3 | ✅ 存在 | `D:\Xilinx2018.3\Vivado\2018.3\bin\vivado.bat` |
| 2018.3 license | ✅ 存在 | `D:\Xilinx2018.3\license\vivado_lic2037.lic` |
| FMSH IP patch（`increment_bit_cfg_v3 -disable_icap`） | ✅ 存在 | `fpai_demo_fpga/ip_patch/run.tcl` |
| NPU 完整工程（.xpr/.bd/.edif/约束/脚本） | ✅ 齐全 | `pl_ddr_mandatory_core_v1/fpai_demo_fpga` |
| HDMI 完整工程（.xpr/.bd/约束/脚本） | ✅ 齐全 | `hdmi_framebuffer_ui_v4_fix/fpga/vivado_prj` |

报告头 `Vivado v.2018.3` 与上述 2018.3 安装一致（此前"只找到 2020.2"的疑点已澄清）。

---

## 1. M1 基线复现（关键：先厘清"复现"的口径）

### 1.1 两种"复现"口径（必须先与用户对齐）

**口径 A —— bitgen 复现（字节级一致，可达成）**
在原工程**已布线的 DCP** 上重跑 `write_bitstream` + `increment_bit_cfg_v3 -disable_icap`。
位流写出对给定 DCP + 工具版本是**确定性**的，故 SHA256 可与原 `.bit` 逐字节一致。
现有脚本 `run_bitstream_generate.tcl`（NPU）/ `write_bitstream_*.tcl`（HDMI）即此流程。

**口径 B —— 全量重建（synth→place→route→bitgen，功能等价、非字节一致）**
真正"重建"要跑综合+布局布线。**Vivado PnR 非确定性**：不同 run（甚至同 run 不同种子）
产出的 routed DCP 不同，`.bit` 随之不同。故"全量重建复现原位流 SHA256"**在任何环境（包括
原环境）都无法保证字节一致**，只能保证"时序/DRC 门禁一致 + 位流可上板等价"。

> ⚠️ 这是 M1 的**关键事实**：若把"复现原位流"理解为字节级 SHA 一致，则只能走口径 A
> （bitgen 复现）；口径 B 是功能复现，不能拿 SHA 比对作门。请用户在启动长构建前确认按
> 哪个口径验收 M1。

### 1.2 M1 复现脚本（现成，不新写）

- **NPU**：`run_bitstream.bat` → `vivado.bat -mode batch -source run_bitstream_generate.tcl`
  （口径 A）。全量口径 B 需另走 `fmsh_synthesis_pre_safe.tcl` + `run_impl_route.tcl` +
  `run_impl_bitstream.tcl` 链。
- **HDMI**：`vivado_prj/` 下 `build_phase1b.tcl` / `write_bitstream_launch.tcl` +
  `call_procise_disable_icap.bat`。

### 1.3 M1 执行方式（建议，待用户确认）

在新工程 `fpga/` 下**复制**原工程到 `fpga/npu_baseline/` 与 `fpga/hdmi_baseline/`（复制前
先 `sha256sum` 记录原工程关键资产，**绝不改原工程**），然后在副本里跑口径 A 先做字节级
复现验证（快、几分钟），再按需跑口径 B 全量重建（数小时）。副本内 `.xpr`/`.bd` 的绝对
路径需在打开后 `update_compile_order`/重生成 wrapper 修正，这一步是 M1 的实质风险点。

---

## 2. M2 —— frame_ctrl 接入 NPU 基线（设计，已读源）

### 2.1 关键架构事实（决定 M2 怎么做）

两工程对 `User_GP0` 的**连接拓扑不同**：

- **NPU 工程** `ps_ai_peripheral.sv`：
  `User_GP0 → u_gp0_io → gp0_manager(GP0_BASE=0x40000000)`，再扇出 4 个子主：
  `host_ctrl`(**RFU 未用**)、`ai_ra`(**RFU 未用**)、`cam`(→`frame_trans` 摄像显示)、
  `user_op`(→`User_Reg`=NPU 控制寄存器)。`host_ctrl`/`ai_ra` 现接 `gpx_RFU`(ERR=0xA0AAAAAA)。
- **HDMI 工程** `hdmi_framebuffer_720p_top.sv`：
  `User_GP0 → axi3_to_axilite_bridge → frame_ctrl`（**直连，无 gp0_manager**）。

- `frame_ctrl` 是 **AXI-Lite 从**（9-bit 地址，版本 `slv_reg3@0x0C=0x20230218`、
  缓冲选择 `slv_reg20@0x50`、帧基址 `slv_reg21@0x54`）。
- `frame_trans` 是 NPU 工程自己的"类 frame_ctrl"模块，接的是 `mna_gp_ww_itf`（FMSH 内部
  协议），**不是** AXI-Lite。
- 软件 `DirectFramebufferBackend` 写的是 **0x40080000（User_GP0）**。

### 2.2 M2 候选方案（实施时择一，需先在综合前核对地址译码）

- **方案①（镜像 HDMI，最干净）**：在 NPU 顶层把 `User_GP0` 经 `axi3_to_axilite_bridge`
  接 `frame_ctrl`，绕过 gp0_manager 的 host_ctrl RFU。前提：确认合并后 User_GP0 的
  0x40080000 译码不被 gp0_manager 占用（Phase 0 地址审计已判 4 段互不重叠，倾向可行）。
- **方案②（复用 host_ctrl RFU 槽）**：在 gp0_manager 的 `host_ctrl` 子主后接一个
  `mna_gp_ww_itf→AXI-Lite` 适配器再接 frame_ctrl。缺点：需新写适配器（现无此件）。

> M2 只做"**接入 + 寄存器读/写验证**"（读 `0x0C` 应得 `0x20230218`，写 `0x50/0x54` 再读回
> 一致），不接 HDMI 输出、不接 fb_read_720p（那些是 M3/M4）。因此 M2 可先不实例化 MMCM/
> TMDS，只验 frame_ctrl 的 AXI-Lite 通路与译码正确。

### 2.3 M2 验证项（综合后、位流前）

- 综合干净、无未驱动/多驱动告警（`frame_ctrl` 的 46 个 slv_reg 全部可达）。
- 若 M2 用方案①，需确认 `axi3_to_axilite_bridge`（HDMI 工程 `rtl/axi3_to_axilite_bridge.sv`）
  已复制入新工程并纳入综合源。
- 寄存器 R/W 行为最终仍需板端验证（我禁碰板，M2 的板端 R/W 测试留给用户），本轮只交付
  综合级集成与主机侧可检查项。

---

## 3. 文档修正（Phase 1 指令第 4 条）

- **删除**"地址冲突导致互斥"旧结论 → 改为"**原先尚无同时实例化 NPU 与 HDMI 的位流**"；
  保留"旧位流不具备完整链路能力"。
- **触摸措辞**：`USB0 配置一致` 只证明**逻辑枚举能力**，不证明供电/长期稳定性；
  改为"**TOUCH 与 Pluto 具备同时枚举条件；最终稳定性仍待 Gate C7 实测**"。
- 受影响的旧文档：`docs/COMBINED_FEASIBILITY_AUDIT.md`、`docs/ADDRESS_MAP_AUDIT.md`、
  `README.md`（Phase 0 结论第 1、5 条）——本轮一并修订。

---

## 4. 暂缓（M3-M7，本回合不做）

- **M3** = HP2 + framebuffer 读通路接入；**M4** = HDMI 时钟/输出；**M5** = NPU+HDMI 同例化；
  **M6** = 身份/能力寄存器；**M7** = 完整实现 + 全报告 + 位流 + 板端包。
- `run_gate9_ui.sh` 在合并位流完成前**保持 fail-closed**。

---

## 5. 状态

`READY-FOR-COMBINED-BITSTREAM-IMPLEMENTATION`（Phase 0 完成）→
**Phase 1 进行中**：1GHz 分析已完成；M1 复现口径待确认；M2 设计已就绪、实施待启动。
**未经实机验证绝不标 PASS/READY；我禁碰板 / 禁写 Flash。**
