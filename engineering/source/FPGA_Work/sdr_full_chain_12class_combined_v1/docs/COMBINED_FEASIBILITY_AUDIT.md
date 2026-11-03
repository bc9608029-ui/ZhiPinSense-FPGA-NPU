# 合并位流可行性审计（任务 39e5 最终阶段 §四，Phase 0）

> **结论：具备生成「NPU + HDMI 帧缓冲」合并位流的充分条件，无缺失资产、无地址阻塞。**
> 障碍不在资产/地址，而在 **RTL 集成工作量**（HDMI 驱动器二选一 + 顶层接线 + 时钟/CDC + 时序收敛）。
> 本阶段只审计可行性，**不产生合并位流、不声称任何硬件 PASS**。

## 1. 两个 FPGA 工程入口与顶层

| 项 | NPU 工程 | HDMI 帧缓冲工程 |
|---|---|---|
| Vivado 工程 | `pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.xpr` | `hdmi_framebuffer_ui_v4_fix/fpga/vivado_prj/hdmi_framebuffer_720p.xpr` |
| 顶层模块 | `ai7030_edif_top.v` | `hdmi_framebuffer_720p_top.sv` |
| 核心封装 | `ps_ai_peripheral.sv`（= ps_ai_wrapper + AI_Mate + Mandatory Core + MIG PL-DDR + SDI/cam 显示） | `ps_ai_wrapper.sv`（= 同一 ps_ai.bd 封装）+ `fb_read_720p.sv` + `frame_ctrl` |
| 器件/封装 | Vivado 报 `xc7z030ffg676-2`（实硅 JFMQL30TAI676H） | 同左，一致 |

## 2. NPU IP 资产完整性（§四 fail-fast 项）

| 资产 | 状态 | 证据 |
|---|---|---|
| NPU 物理网表 | ✅ 存在 | `AI_Mate.edif`（`38f14b44…`）+ 变体 `AI_Mate_no_detpost.edif`（`731eb6db…`） |
| 仿真黑盒桩 | ✅ 存在 | `AI_Mate_stub.v`（`61fc9194…`） |
| Mandatory Core RTL | ✅ 存在 | `job_domain_controller.sv` / `pl_ddr_mandatory_core_regs.sv` / `pl_ddr_mandatory_core_engine.sv` / `pl_ddr_mandatory_core_top.sv` + `deps/frozen`（6）+ `deps/adapters`（7） |
| BD | ✅ 存在 | `ps_ai.bd`（`78f5599b…`，与 HDMI 工程 byte-identical） |
| XDC | ✅ 存在 | `ai7030.xdc` / `impl_constraints.xdc` / `pl_ddr_mandatory_core_v1.xdc` / `cdc_async_groups.xdc` |
| 授权/license | ⚠️ 未发现独立 license 文件 | 仅 `bfmlicense_warning.xit`（BFM 仿真 license 警告，非 IP 授权）。**但 AI_Mate 以未加密 EDIF 物理网表交付，无需 Vivado 运行时 license**；此前 NPU 位流已成功构建并上板运行（Gate 7 `matched=227/240`），IP 可用性已实证 |

**判定**：NPU IP 资产**完整、可构建、已上板实证**，无 `BLOCKED-MISSING-COMBINED-BITSTREAM-ASSET`。

## 3. HDMI 帧缓冲 IP 资产完整性

| 资产 | 状态 |
|---|---|
| 顶层/读通路 | ✅ `hdmi_framebuffer_720p_top.sv` / `fb_read_720p.sv` / `axi3_to_axilite_bridge.sv` / `ps_ai_wrapper.sv` |
| 显示核 | ✅ `display/frame_ctrl.v` / `aq_axi_master.v` / `uihdmitx.v` / `timing_gen_xy.v` / `bridge_s.v` / `level_cross.v` / `pulse_cross_camera.v` / `oserdese2_10to1.v` / `frame_fifo_read.v` / `frame_fifo_write.v` / `frame_read_write_largebuf.v` / `video_rect_read_data.v` / `video_define.v` / `color_bar.v` |
| 时钟/FIFO IP | ✅ `ip/clk_wiz_0` / `fifo_1` / `afifo_16i_64o_largebuf` / `afifo_64i_16o_128` |
| XDC | ✅ `hdmi_framebuffer_720p.xdc`（HDMI 引脚 + CDC 异步组 + ASYNC_REG） |
| BD | ✅ `ps_ai.bd`（与 NPU 工程 byte-identical） |

## 4. PS 配置一致性（两工程 byte-identical）

两 `ps_ai.bd` SHA256 完全一致 → **PS7 配置逐字节相同**：FCLK_CLK0=50MHz、PS DDR `MT41K256M16 RE-125`（32-bit）、
USB0 使能、`M_AXI_GP0/GP1` + `S_AXI_HP0/1/2/2_1/3` 使能。合并后 PS 侧无需任何改动。

USB0 使能意味着 **Gate C7 触摸（`1a86:e5e3` USB2IIC_CTP_CONTROL）+ Pluto（`0456:b673`）+ Hub（`0424:2514`）**
在合并位流的 PS 配置下**具备同时枚举条件**（软件 evdev 侧为后续 §七 工作，本阶段只确认 PS 已具备 USB）。
`USB0 配置一致` 仅证明**逻辑枚举能力**，不证明供电/长期稳定性；**TOUCH 与 Pluto 具备同时枚举条件，
最终稳定性仍待 Gate C7 实测**。

## 5. 关键结论：地址不冲突（详见 ADDRESS_MAP_AUDIT.md）

`ps_ai.bd` 地址图 = 4 段互不重叠的 512K 窗口：`0x40000000`(NPU) / `0x80000000`(NPU DMA) /
`0x40080000`(frame_ctrl) / `0x80080000`。**NPU 与 frame_ctrl 可同一位流共存。**
此前 ui_v1 的 "地址冲突导致互斥" 结论基于错误的 1MiB 假设，已被权威 BD 地址图推翻：
真实原因是**原先尚无同时实例化 NPU 和 HDMI 的位流**，且**旧位流不具备完整链路能力**。

## 6. 剩余风险（集成工作量，非资产阻塞）

1. **HDMI 驱动器二选一（唯一硬集成点）**：NPU 工程 `ps_ai_peripheral` 内部 SDI/cam→HDMI 显示通路
   与 HDMI 工程的 `fb_read_720p` 都要驱动同一组 HDMI 引脚（AC17/AA15/Y16/W16）。
   合并必须停用 NPU 侧显示通路、让 `fb_read_720p` 独占 HDMI。
2. **时序**：NPU 工程已知 BUFG 1GHz min-period 项（Required 1.409ns / Actual 1.000ns / Slack −0.409ns）。
   合并新增逻辑+时钟域可能恶化时序，需重跑综合/实现并满足 §六硬门（WNS≥0/WHS≥0/TNS=0/THS=0/DRC 0 error）。
3. **资源**：xc7z030 同时承载 NPU+MIG PL-DDR+SDI(可裁)+HDMI 帧缓冲。
4. **CDC**：MIG DDR 时钟、SDI GTX 时钟（可裁）、HDMI MMCM 时钟、PS7 FCLK 多域（见 CLOCK_RESET_CDC_AUDIT.md）。

## 7. 最小合并方案（§五-§六 实施预览，Phase 0 不执行）

1. 基座 = NPU 工程（`ai7030_edif_top` + `ps_ai_peripheral`：AI_Mate + Mandatory Core + MIG PL-DDR）。
2. 停用 `ps_ai_peripheral` 内部 SDI/cam→HDMI 显示通路（HDMI 引脚让给帧缓冲）。
3. 接入 HDMI 帧缓冲读通路：`fb_read_720p` + `frame_ctrl` + `axi3_to_axilite_bridge` + MMCM3(200→100MHz hp_clk)，
   接 `User_GP0`(0x40080000) + `S_AXI_HP2_1` + HDMI 引脚。
4. 合并 XDC：NPU（SDI GTX 时钟/MIG/PLLE2 LOC）+ HDMI（CDC 异步组/ASYNC_REG 标签/MMCM 时钟组）。
5. 时钟/复位/CDC 协调 + 时序收敛 + 新位流标识符。

## 8. 状态红线（§十一 + Gate C7）

- Phase 0 完成态 = **READY-FOR-COMBINED-BITSTREAM-IMPLEMENTATION**（可行性已审计，实施未开始）。
- 后续：实施+主机/仿真测试 → `READY-FOR-COMBINED-BITSTREAM-HARDWARE-TEST`；C1-C6 板测通过 → `FULL_CHAIN_HARDWARE_PASS`；
  C1-C7 全部通过 → `FULL_CHAIN_WITH_TOUCH_HARDWARE_PASS`。
- 本阶段**绝不**声称合并位流存在、绝不写任何 PASS。
- 绝不伪造合并位流、绝不 Golden/Mock 回放冒充实时、绝不动 4 个保护原工程、禁碰板、禁写 Flash。
