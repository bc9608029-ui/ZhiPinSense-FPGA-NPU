# Phase 0 审计报告 — HDMI 动态显示与触摸上板

> 审计对象：① 已验证的 720p 色条工程（`F:\FPGA_Work\hdmi_board_bringup_v1`）；
> ② 官方 demo RTL（`F:\嵌赛\tmp_official_fpga_audit\fpai_demo_fpga`）；
> ③ 官方 demo 应用（`F:\嵌赛\tmp_official_app_audit\fpai_demo_app`）；
> ④ UI 工程（`F:\FPGA_Work\hdmi_ui_v1_1`）。
> 结论只陈述**从源码/文档可证的事实**，未证实的项一律标"待确认"，不猜测。

---

## 0. 一句话结论

**动态 DDR 帧缓冲的核心寄存器与数据路径已从官方 RTL + 应用双向确认**（`0x40080054` = 显示读帧地址寄存器，写"帧缓冲字节地址>>3"，格式 RGB565）。但发现**两个必须由你拍板的关键事实**：

1. 三处分辨率不一致（色条 1280×720 / 官方 demo 1920×1080 / UI 布局 1024×600）；
2. 动态帧缓冲需要 **PS7 + DDR3**，而已验证色条是**纯 PL 无 PS/DDR**——二者是两种架构，"替换数据源"≠"加 DDR"，必须新建带 PS+DDR 的工程。

---

## 1. 已确认：帧控制寄存器映射（基址 `0x40080000`）

来源：`fpai_demo_fpga/rtl/display/frame_ctrl.v`（AXI-Lite 从设备，`S_AXI_AWADDR[8:0]` 译码，
寄存器 `slv_reg0..45`，4 字节步进）＋ `fpai_demo_app/.../et_device.hpp` 与
`hdmi_display.hpp` 的双向印证。

| 偏移 | 寄存器 | 名称 | 复位值 | 说明 |
|---|---|---|---|---|
| `0x000` | slv_reg0 | irq_test | 0 | `[0]` 中断测试 |
| `0x004` | slv_reg1 | aclk_frame_req | 0 | 写 1 触发一次取帧（读回） |
| `0x008` | slv_reg2 | frame_en_switch | 0 | 帧显示开关 |
| `0x00C` | slv_reg3 | frame_ctrl_ver | — | 只读版本 |
| `0x010` | slv_reg4 | wr_buf_index | — | 只读，写缓冲索引 |
| `0x014` | slv_reg5 | rd_buf_index | — | 只读，读缓冲索引 |
| `0x018` | slv_reg6 | img_en | 0 | 图像使能 |
| `0x01C` | slv_reg7 | icore_pre_ov | 0 | 内核预处理溢出 |
| `0x020` | slv_reg8 | resize_confh | 0 | 水平 resize `[3:0]` |
| `0x024` | slv_reg9 | resize_confv | 0 | 垂直 resize `[3:0]` |
| `0x028..0x03C` | slv_reg10..15 | resize x0/y0/x1/y1/x_len/y_len | 0 | 裁剪窗口参数 |
| `0x040` | slv_reg16 | cnt_clr | 0 | 计数清零 |
| `0x044` | slv_reg17 | continuous_mode | 0 | 连续模式 |
| `0x048` | slv_reg18 | network_running | — | 只读 |
| `0x04C` | slv_reg19 | plin_valid | 0 | PL 输入有效 |
| `0x050` | slv_reg20 | **camera_wr_addr** | `0x7C0_0000` | 相机写帧地址（27 位） |
| `0x054` | slv_reg21 | **camera_rd_addr** | `0x7E0_0000` | **显示读帧地址（27 位）** |
| `0x058..0x090` | slv_reg22..36 | camera_wr_done / 计数器 | — | 帧完成/计数诊断 |
| `0x08C` | slv_reg35 | over_thr | 98000 | 超时阈值（注释：1080p=2200×44） |
| `0x094` | slv_reg37 | H_SYNC | 44 | 水平同步脉宽 |
| `0x098` | slv_reg38 | H_BACK_PORCH | 148 | 水平后肩 |
| `0x09C` | slv_reg39 | H_ACTIVE | **1920** | 水平有效 |
| `0x0A0` | slv_reg40 | H_FRONT_PORCH | 88 | 水平前肩 |
| `0x0A4` | slv_reg41 | V_SYNC | 5 | 垂直同步 |
| `0x0A8` | slv_reg42 | V_BACK_PORCH | 4 | 垂直后肩 |
| `0x0AC` | slv_reg43 | V_ACTIVE | **1080** | 垂直有效 |
| `0x0B0` | slv_reg44 | V_FRONT_PORCH | 36 | 垂直前肩 |
| `0x0B4` | slv_reg45 | **vtc_enable** | 0 | VTC 使能（= `et_device.hpp` 的 `0x40080000+0xB4`） |

> 官方 demo 的时序默认是 **1080p60**（H 2200 × V 1125，H_ACTIVE=1920/V_ACTIVE=1080），
> 与 `over_thr=98000` 的注释（"for 1080p = 2200*44 pix"）自洽。

---

## 2. 已确认：`0x40080054` 的准确含义（指令要求核实的寄存器）

**`0x40080054` = `frame_ctrl` 的 `slv_reg21` = `camera_rd_addr` = 显示从 DDR 读帧缓冲的起始地址。**

双向证据：
- **RTL 侧** `frame_ctrl.v:701-709`：`slv_reg21 = camera_rd_addr`，复位 `27'h7E0_0000`。
- **应用侧** `hdmi_display.hpp:88`：`DISPLAY_READ_ADDR = 0x40080054`；
  `hdmi_display.hpp:41`：`write(DISPLAY_READ_ADDR, display_chunk_->begin.addr() >> 3)`。

**写入值 = 帧缓冲字节物理地址右移 3 位（即 8 字节对齐的"字地址"），有效 27 位。**

完整地址链（全部经源码确认）：
```
PS:  write(0x40080054, addr >> 3)
       │
       ▼
frame_ctrl.camera_rd_addr[26:0]           (27 位)
       │
       ▼
frame_to_ps_largebuf: read_addr = camera_rd_addr[26:0]
       │  (frame_to_ps_largebuf.v:298-301)
       ▼
frame_read_write_largebuf.rd_burst_addr   (27 位)
       │  (frame_to_ps_largebuf.v:451: .RD_ADRS({rd_burst_addr, 3'd0}))
       ▼
aq_axi_master.RD_ADRS = {rd_burst_addr, 3'b0}   ← 左移 3 位 = 恢复字节地址
       │  (aq_axi_master.v:414: M_AXI_ARADDR = reg_rd_adrs)
       ▼
M_AXI_ARADDR = addr（字节地址），PL 经 HP 端口读 DDR
```

> 为什么 `>>3`：`aq_axi_master` 是 64 位（8 字节）数据总线，帧缓冲按 8 字节对齐；
> 寄存器 27 位 + 隐式 3 位 = 30 位字节地址，覆盖 1 GB 地址空间，足够容纳 DDR 映射区。

---

## 3. 已确认：像素格式与数据路径

- **像素格式 = RGB565**（每像素 2 字节，16bpp）。
  - 应用侧 `hdmi_display.hpp:10-14, 32`：注释"输入数据为 RGB565"、`buffer_size = W*H*2`。
  - RTL 侧 `frame_read_write_largebuf.v:26-27`：`READ_DATA_BITS = 16`、`WRITE_DATA_BITS = 16`。
- **DDR 读路径**：`frame_read_write_largebuf`（`MEM_DATA_BITS=64`，每 burst 从 DDR 读 64 位 = 4 个 RGB565 像素）→ 拆成 16 位 → `video_rect_read_data` → 显示。
- **DDR 型号 = DDR3**（`fpai_demo_fpga/.../ps7_init.html` 全为 DDR3 参数；由 PS7 DDR 控制器管理）。
- **多缓冲**：`frame_read_write_largebuf` 提供 `read_addr_0..3` 四个基地址 + `read_addr_index`
  选择（`frame_read_write_largebuf.v:46-50`），配合 `wr_buf_index`/`rd_buf_index`（slv_reg4/5）
  构成 4 缓冲切换，**double-buffer 的 RTL 机制已具备**。

---

## 4. 关键发现一：三处分辨率不一致

| 来源 | 分辨率 | 像素时钟 | 说明 |
|---|---|---|---|
| 已上板色条工程 | **1280×720@60** | 74.25 MHz | 已验证，RGB888（color_bar 输出 24 位） |
| 官方 demo 显示 | **1920×1080@60** | 148.5 MHz | RGB565，寄存器默认 H_ACTIVE=1920/V_ACTIVE=1080 |
| hdmi_ui_v1_1 布局 | **1024×600** | — | `DESIGN.md:16` "native 1024×600, touch via USB" |

**含义**：UI 按 1024×600 设计（`DESIGN.md` 明确），但 HDMI 输出必须给屏幕一个它认识的标准
时序。已上板验证的是 720p。因此 Phase 2 的 1024×600 UI 需要**缩放到 720p**（或 letterbox）
输出——这个映射策略是 Phase 2 的待决项，Phase 1 先固定 **1280×720** 输出（沿用已验证时序）。

---

## 5. 关键发现二：纯 PL 色条 → 动态 DDR 帧缓冲的架构鸿沟

- **已上板色条**：纯 PL（无 PS7、无 DDR、无 MIG），只有 200 MHz 晶振 → MMCM → HDMI。
  顶层 `hdmi_colorbar_720p_top.v` 仅实例化 IBUFDS/MMCM/color_bar/uihdmitx。
- **动态帧缓冲**：必须由 **PS 写 DDR**，**PL 读 DDR**。而 7z030 的 DDR 控制器在 PS7 内，
  PL 只能经 PS7 的 HP 端口访问 DDR。**没有 PS7 就没有 DDR 访问。**
- 官方 demo（`fpai_demo_fpga`）是完整的 PS7+DDR3+HP 系统，但它是 1080p + SDI + NPU 的
  完整设计，不能直接剥离复用。

**因此 Phase 1 不是"替换色条数据源"，而是"从纯 PL 升级为 PS+DDR+PL 系统"。** 这需要：
1. 新建 Block Design（PS7 + DDR3 配置 + AXI 互联 + HP 端口 + 地址映射）；
2. PL 侧帧读模块（自写 720p 时序 + `aq_axi_master` 读 DDR + RGB565→RGB888→uihdmitx）；
3. PS 侧 C 程序（写 RGB565 帧到 DDR，写 `0x40080054`），需要交叉编译工具链。

---

## 6. 待确认项（缺失证据，不猜测）

| 项 | 状态 | 需要的证据 |
|---|---|---|
| DDR3 容量（128/256/512 MB？） | 待确认 | 板子规格书或 BD/MIG 配置里的内存型号 |
| PS 侧写 DDR 后 PL 读的缓存一致性 | 待确认 | udma 是否 uncached/reserved；是否需要 `flush`/`msync` |
| PS 侧 C 程序运行方式 | 待确认 | baremetal（SDK/Vitis）还是板载 Linux `/dev/mem`；板载 Linux 无 framebuffer/DRM（指令已声明） |
| 交叉编译工具链 | 待确认 | 是否有 SDK/Vitis、是否装好了交叉编译器 |
| 板子 PS 启动方式 | 待确认 | 当前上板系统是裸跑还是 Linux；PL 程序是否要在 Linux 下配合 |
| Touch USB 宿主 | 待确认 | USB 触摸连**板子 PS USB host**（读 `/dev/input/event*`）还是连 **PC**；Phase 3 再定 |
| 1024×600 → 720p 缩放策略 | 待确认 | Phase 2 再定（scaler 缩放 / letterbox / 直接改 UI 到 720p） |

---

## 7. 架构决策点（需要你拍板，决定 Phase 1 方向）

Phase 1 的最小可行路径有两条，工作量与风险差别很大：

- **路径 A（真 DDR 帧缓冲，指令原文方向）**：新建 PS7+DDR3 的 Block Design，PS 写 DDR，
  PL 读 DDR→720p HDMI。**能真正验证"PS 写 DDR→PL 读→HDMI"全链路**，但需要搭 BD、配 DDR、
  交叉编译 PS 程序，命令行环境下风险与工作量都高。
- **路径 B（纯 PL + 片内 BRAM 帧缓冲，中间过渡）**：不碰 DDR，PL 内部把测试图案写进
  BRAM，再按"RGB565 帧读"路径读出送 720p HDMI。**先验证"帧读 + RGB565→RGB888→HDMI"
  的 PL 逻辑正确**，但**不涉及 PS/DDR**，是路径 A 的降级验证，不是真 DDR。

建议：**路径 B 先跑通"帧读→HDMI"的 PL 侧逻辑（零架构风险），再上路径 A 接真 DDR**。
但这偏离"真 DDR 动态帧缓冲"的严格验收，需要你确认取舍。

---

## 8. 下一步最小上板步骤（等你拍板架构后执行）

> 以下为**待执行**步骤，不是"已完成"。本轮不写 Flash、不 claim 上板。

1. **你先确认第 7 节路径**：A（真 DDR）还是 B（纯 PL BRAM 过渡）。
2. 我按选定路径，在 `F:\FPGA_Work\hdmi_framebuffer_ui_v1\` 下新建工程，
   沿用已验证 720p 的 HDMI TMDS 引脚 / 74.25 MHz 时序 / MMCM / TMDS_33 /
   FMSH `disable_icap` 流程，只替换数据源。
3. Vivado 2018.3（`D:\Xilinx2018.3\Vivado\2018.3`）真实综合/实现/出位流，
   过 DRC 0 Error + 时序 + 位流 SHA 三道门。
4. 给你**逐行 JTAG 临时加载**步骤（复用色条包的 `_disable_icap.bit` 加载方式，
   不写 Flash，断电回退），并给出 6 种测试图案（红/绿/蓝/棋盘/RGB565 渐变/计数）的
   观察判据与失败现场收集方法。

**在你回复路径 A/B 之前，我不会开始写任何 RTL 或搭 BD。**
