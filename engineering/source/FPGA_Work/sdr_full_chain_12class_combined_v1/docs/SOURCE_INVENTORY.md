# 来源资产清单（任务 39e5 最终阶段 §三）

> 记录合并位流工程用到的两个 FPGA 工程来源文件（相对 `F:\FPGA_Work`），SHA256 见
> `SOURCE_PROVENANCE_SHA256.txt`。四个保护原工程**绝不修改**，本工程只引用/复制。

## 1. NPU FPGA 工程（`pl_ddr_mandatory_core_v1`）

| 文件 | 角色 |
|---|---|
| `fpai_demo_fpga/rtl/ai7030_edif_top.v` | NPU 工程顶层（PS DDR + PL DDR + SDI + HDMI + PJTAG） |
| `fpai_demo_fpga/rtl/ps_ai_peripheral.sv` | 核心封装 = ps_ai_wrapper + AI_Mate + Mandatory Core + MIG PL-DDR + SDI/cam 显示 |
| `fpai_demo_fpga/rtl/AI_Mate_stub.v` | NPU 黑盒仿真桩 |
| `fpai_demo_fpga/rtl/edif/AI_Mate.edif` | NPU 物理网表（真实推理逻辑） |
| `fpai_demo_fpga/rtl/edif/AI_Mate_no_detpost.edif` | NPU 网表变体（无 det-post） |
| `fpai_demo_fpga/fpai_demo_vivado.srcs/sources_1/bd/ps_ai/ps_ai.bd` | PS_AI Block Design（processing_system7 + AI 接口 + 4 段地址图） |
| `fpai_demo_fpga/constrs_1/ai7030.xdc` | NPU 时序约束（PLLE2 LOC / SDI GTX 时钟 / false_path） |
| `fpai_demo_fpga/constrs_1/impl_constraints.xdc` | NPU 引脚约束（HDMI/SDI/PJTAG/led/sys_clk） |
| `pl_ddr_integration_v1/rtl/job_domain_controller.sv` | Mandatory Core：作业域控制 |
| `pl_ddr_integration_v1/rtl/pl_ddr_mandatory_core_regs.sv` | Mandatory Core：寄存器 |
| `pl_ddr_integration_v1/rtl/pl_ddr_mandatory_core_engine.sv` | Mandatory Core：引擎 |
| `pl_ddr_integration_v1/rtl/pl_ddr_mandatory_core_top.sv` | Mandatory Core：顶层 |
| `pl_ddr_integration_v1/pl_ddr_mandatory_core_v1.xdc` | Mandatory Core 约束 |
| `pl_ddr_integration_v1/cdc_async_groups.xdc` | Mandatory Core CDC 异步组 |
| `pl_ddr_integration_v1/deps/frozen/*.sv`（6 文件） | 冻结数据通路（qam_feature_pipeline / mandatory_core_path / iq_stream_fifo / iq_frame_controller / feature_quantizer / tensor_packer） |
| `pl_ddr_integration_v1/deps/adapters/*.sv`（7 文件） | 适配器（async_fifo_gray / user_ddr_iq_reader / iq_beat_unpacker / pl_ddr_iq_input_adapter / tensor_plane_beat_packer / user_ddr_tensor_writer / pl_ddr_tensor_output_adapter） |

## 2. HDMI 帧缓冲 FPGA 工程（`hdmi_framebuffer_ui_v4_fix`）

| 文件 | 角色 |
|---|---|
| `fpga/rtl/hdmi_framebuffer_720p_top.sv` | HDMI 帧缓冲顶层（PS7 + fb_read_720p + frame_ctrl + 720p HDMI） |
| `fpga/rtl/ps_ai_wrapper.sv` | 同一 ps_ai.bd 的 RTL 封装（与 NPU 工程共用） |
| `fpga/rtl/fb_read_720p.sv` | 帧缓冲读通路（S_AXI_HP2_1 → DDR 帧缓冲 → TMDS） |
| `fpga/rtl/axi3_to_axilite_bridge.sv` | User_GP0(AXI3) → frame_ctrl(AXI-Lite) 桥 |
| `fpga/rtl/display/frame_ctrl.v` | 帧缓冲控制寄存器（版本/缓冲选择/帧基址） |
| `fpga/rtl/display/aq_axi_master.v` | 帧缓冲 AXI 读主（非对称 FIFO 读侧，v4_fix 已修半字序） |
| `fpga/rtl/display/uihdmitx.v` / `timing_gen_xy.v` / `oserdese2_10to1.v` | HDMI TMDS 编码 + 时序 |
| `fpga/rtl/display/bridge_s.v` / `level_cross.v` / `pulse_cross_camera.v` | CDC 同步器 |
| `fpga/rtl/display/frame_fifo_read.v` / `frame_fifo_write.v` / `frame_read_write_largebuf.v` / `video_rect_read_data.v` / `video_define.v` / `color_bar.v` | 帧缓冲 FIFO + 显示后端 |
| `fpga/rtl/ip/clk_wiz_0` / `fifo_1` / `afifo_16i_64o_largebuf` / `afifo_64i_16o_128` | 时钟/异步 FIFO IP |
| `fpga/constrs/hdmi_framebuffer_720p.xdc` | HDMI 引脚 + CDC 异步组 + ASYNC_REG 标签 |
| `fpga/bd/ps_ai/ps_ai.bd` | 与 NPU 工程 byte-identical |

## 3. 关键一致性结论

- 两 `ps_ai.bd` byte-identical（`78f5599b…`）→ PS 配置 + 地址图一致。
- 两工程 HDMI 引脚（AC17/AA15/Y16/W16）一致。
- NPU = AI_Mate.edif（未加密网表）+ Mandatory Core RTL；均已上板实证可构建/运行。

## 4. 软件侧（后续 §七 再复制登记）

`npu_realtime_v1`、`hdmi_framebuffer_ui_v4_fix/sw`、`sdr_full_chain_12class_v1`、
`sdr_full_chain_12class_ui_v1` 的软件源在 §七 复制进 `board_package/ sdr_adapter/ ui_sw/` 时
再逐文件登记 SHA256，本阶段（Phase 0）不复制软件。
