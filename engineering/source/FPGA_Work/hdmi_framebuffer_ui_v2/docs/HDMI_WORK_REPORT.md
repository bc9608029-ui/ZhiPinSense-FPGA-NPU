# HDMI 显示系统 · 完整工作报告

> 报告日期：2026-10-04
> 状态：**全部 `READY-FOR-HARDWARE-TEST`（构建通过，未上板）**——未经实机验证，任何阶段不写 `PASS` / `READY` / "显示成功"。

---

## 1. 目标与范围

在 FMQL30TAI（悟净）开发板上打通「识别结果 → 屏幕显示 → 触摸交互」这条**显示与交互子系统**，作为最终射频认知系统的前端。

本阶段是**独立验收**：先逐门验证显示/触摸链路本身（用演示数据），再接 NPU 真实推理结果。独立验收是为了故障可定位——显示链先单独 PASS，之后接上真结果若出错，能分清是"显示问题"还是"推理问题"。

**显示器**：7" IPS 触摸屏，原生 **1024×600**（300nit），HDMI 输入（720p 由屏内缩放芯片缩到面板），触摸 = **USB HID**。

---

## 2. 硬件与工具链

| 项 | 值 |
|---|---|
| 板卡 | FMQL30TAI（悟净），Vivado part `xc7z030ffg676-2` |
| 显示器 | 7" IPS 触摸屏 1024×600（HDMI 口 + touch 口；touch=USB HID，USB 线同线供电+触摸） |
| 构建 | Vivado **2018.3**（`D:\Xilinx2018.3`，FMSH patch 官方配对版本） |
| 下载 | Vivado **2020.2** Hardware Manager（只下载，临时 JTAG，volatile） |
| FMSH patch | `source $JFM_PATH/ip_patch/run.tcl` + `add_hook_tcl_to_prj`，`JFM_PATH=D:/FMSH/JFM_Kits` |
| PS 编译 | 板载 Linux，`g++ -std=gnu++17`，**无 iCraft/NPU 依赖**——直连后端仅链接 libc |
| 上电 | 12V DC 接 J37，拨 SW8 上电 |

**接线要点**：HDMI 口 ← 板子 PL 侧 pHDMI（直接接）；touch 口（USB）← 板子 USB host（同一根线同时供电+触摸）；**不要按屏的 POWER 键**（USB 上电即自动开机，按 POWER=关机；供电不稳才单独接 POWER 口）。

---

## 3. 显示数据通路（架构）

```
PS DDR3（RGB565 16bpp，1280×720）
   ↓  PS7 S_AXI_HP2_1 端口
aq_axi_master 读（64-bit burst，read_len = 27'd230400 字）
   ↓  frame_fifo / 行缓存（BRAM 仅作 FIFO，不存完整帧）
fb_read_720p（双缓冲：read_addr_0/1，read_addr_index = {1'b0, 同步后的 camera_wr_addr[0]}）
   ↓
TMDS 720p@60 输出（uihdmitx，TMDS_33）
   ↓  PL pHDMI → 屏内缩放 → 1024×600 面板
```

**关键寄存器**（frame_ctrl）：
- `0x40080054` = 帧基址 >> 3（读地址，PS 写一次）
- `0x40080050` = 后缓冲号 bit[0]（双缓冲原子切读）
- `0x4008000C` = 版本 `0x20230218`

**时钟链**：200MHz 晶振 → MMCM1 27MHz → MMCM2 74.25/371.25MHz；MMCM3 → 100MHz；PS7 FCLK 50MHz → clk_wiz_0 → 100MHz。

---

## 4. 各阶段成果（验收门链）

| 门 | 阶段 | 位流 | PS 程序 | 测什么 | 状态 |
|---|---|---|---|---|---|
| — | 色条 | v1 纯 PL | 无 | 720p 时序 + TMDS + HDMI 链路 | 构建通过，未上板 |
| 门1 | 1A 静态帧 | v1 单缓冲 | `phase1a_fb_test` | DDR 读通路 + 静态 RGB565 帧 | 构建通过，未上板 |
| 门2 | 1B 动态双缓冲 | v3 双缓冲 | `phase1b_doublebuf_test` | 移动竖条无撕裂 | 编译+host 测试通过，未上板 |
| 门3 | 1C 稳定性 | v3 双缓冲 | `phase1c_dynamic_test` | 4 图案 ≥10min 稳定 | 编译+host 测试通过，未上板 |
| 门4 | 2 完整 UI | v3 双缓冲 | `phase2_ui_render` | 识别 UI（10 类+置信度+Top-1）离屏渲染 | 编译+host 测试通过，未上板 |
| 门5 | 3 触摸 | v3 双缓冲 | `phase3_touch_test` | USB 触摸检测/标定/翻页 | 编译+host 测试通过，未上板 |

**位流数量**：3 个——色条（纯 PL）、1A（单缓冲）、1B/1C/2/3（共用 v3 双缓冲，只换 PS 程序）。

**验收门链（顺序执行，任一未过不得进入下一阶段）**：
`色条 → 1A 静态帧 → 1B 动态双缓冲 → 1C 稳定性 → 2 完整 UI → 3 触摸`

---

## 5. 构建结果（已通过）

| 位流 | WNS | WHS | TNS/THS | DRC | 产物 |
|---|---|---|---|---|---|
| 色条 v1 | +4.794 | +0.125 | — | 0 Error（3 无害 warning） | `.bit` + `_disable_icap.bit` |
| 1A 单缓冲 | +3.557 | +0.030 | 0 / 0 | 0 Error 0 Warning | `.bit`(sha256 `99ec18b6…`) + `_disable_icap.bit`(`ec162e2d…`) |
| v3 双缓冲 | +3.427 | +0.037 | 0 / 0 | 0 Error（24 无害 warning） | `.bit`(`fdc93f10…`) + `_disable_icap.bit`(`686bb1e3…`) |

- v2 的 24 条 warning 全无害：REQP-1839×20（官方读 FIFO 异步复位固有结构）、RTSTAT-10×1（相机写路径 tie-off）、PORTPROP-2×2（sys_clk DIFF_TERM）、CHECK-3×1（条数上限），**非双缓冲改动引入**。
- `_disable_icap.bit` 由 FMSH 补丁 `write_bitstream_post` 钩子**自动产出**，是临时 JTAG 加载目标（**永不写 Flash**）。
- **时钟约束 + CDC 已修正（2026-10-04）**：XDC 改为按 pin 引用时钟（消 TIMING-28）、对 22 个同步器寄存器打 `ASYNC_REG`（消 CDC-2/TIMING-10）；缓冲选择由 2-bit 多 bit 跨域改为 1-bit 双触发同步（消 CDC-6）。剩余 CDC/methodology 警告逐条书面豁免于 `docs/CDC_WAIVERS.md`。本轮位流 WNS +3.427、WHS +0.037。

---

## 6. 关键 RTL 改动（v1 单缓冲 → v3 双缓冲）

- `fb_read_720p.sv`：`read_addr_1 = camera_rd_addr + 27'd230400`（buffer1 = buffer0 + 一帧 720p）；缓冲选择 `camera_wr_addr[0]` 经 1-bit 双触发同步（`buf_sel_sync1/2`）后驱动 `read_addr_index = {1'b0, 选择}`（PS 写 `0x40080050`，每帧翻转）。
- `hdmi_framebuffer_720p_top.sv`：新增 `camera_wr_addr` 连线，`camera_wr_addr[0]` 接 `read_buf_sel`。
- **冻结未动**：720p HDMI 时序、TMDS 引脚、时钟链、`ps_ai.bd` PS7/DDR3 配置。

---

## 7. 最新确认（2026-10-04）：安全显示后端重构 + Phase 3 升级

- **显示器硬件确认**：7" IPS 1024×600 触摸屏，HDMI 输入 720p（屏内缩放），touch 口 = USB HID（USB 线同线供电+触摸，不按 POWER）。→ **现有 720p 位流不改**，缩放交给屏。
- **去掉 iCraft `Device::Open`（安全显示后端）**：HDMI-only 位流没有 NPU，旧 `Device::Open("axi://...?npu=...&dma=...")` 会**卡死板子 Linux**。四个 PS 程序（1B/1C/2/3）全部改为 `direct_framebuffer_backend`：读 sysfs 得 phys/size → mmap `/dev/udmabuf0`（RGB565）+ mmap `/dev/mem` 单页（frame_ctrl）→ **版本校验后才写寄存器，每次写都读回校验** → msync（容忍 EINVAL）+ `sync_for_device`。后端带 host mock 测试（9 类断言，0 失败）。
- **Phase 3 升级**：① 触摸设备**枚举 `/dev/input/event*`** 自动发现（不硬编码 event 编号），名字关键字（`touch/egalax/goodix/ilitek/ft5/gt9/ch5/wch`）+ ABS 能力双命中；② 事件循环 SYN_REPORT 感知，**兼容单点（BTN_TOUCH）+ 多点协议 B（ABS_MT_TRACKING_ID）**；③ 找不到触摸 → 打印 `PHASE3_TOUCH_FAIL` 并**非零退出（不假 PASS、不自动翻页）**。
- **防卡死**：`build_on_board.sh run` 支持 `RUN_TIMEOUT` 用 `timeout --kill-after=5s` 兜底；运行前校验 `/dev/udmabuf0`/`/dev/mem` 存在；运行后打印 `POST-RUN_SHELL_OK` 确认 shell 恢复。

---

## 8. 与主系统（NPU 识别）的关系

**当前独立，未结合。** Phase 2 的 UI 是"真框架、假数据"——10 类名/置信度条/Top-1/触摸都是真的，但置信度是 `make_conf()` 归一化演示 softmax，不是 NPU 输出。

**结合点唯一且轻**：把 `make_conf()` 换成「NPU 输出 10 类 logits → softmax → 置信度」，UI 即变成真识别结果。同一位流、同一 HDMI 链路、同一触摸，**只动 PS 程序里"数据从哪来"一处**。

完整链路（最后一段已单独验收，未接真 NPU 输出）：

```
SDR → IQ → PL DDR → NPU(10类) → 结果 → [本阶段: UI渲染 + HDMI显示 + 触摸]
        └—— 之前的系统链路 ——┘        └—— 尚未接真 NPU 输出 ——┘
```

---

## 9. 红线遵守情况

- 只临时 JTAG（volatile），**永不写 Flash**；加载 `*_disable_icap.bit` 而非原始 `.bit`。
- 720p 时序 / TMDS 引脚 / 时钟链 / `ps_ai.bd` 冻结复用官方。
- 完整帧用真实 DDR3（BRAM 仅作 FIFO/行缓存）。
- **不碰 NPU / DMA / `Device::Open`**；直连 `/dev/udmabuf0` + `/dev/mem`（版本门禁后写寄存器，每次读回校验）。
- 独立目录工作，不覆盖已有工程/全局配置。
- 未上板 → 只标 `READY-FOR-HARDWARE-TEST`，不标 PASS/READY。

---

## 10. 待办（只能你上板）

1. **色条上屏**：临时 JTAG 加载色条 `_disable_icap.bit`，验 720p 时序 + HDMI 链路 + 屏缩放 720p（顺带确认屏能吃 720p）。
2. **1A → 1B → 1C → 2 → 3** 逐门 PASS（任一 FAIL 即停，收集证据）。
3. **Phase 3 实测触摸**：看 `TOUCH_FOUND` / `PHASE3_TOUCH_FAIL`，触摸坐标对位（屏缩放是拉伸还是留黑边）上板后微调。
4. **显示链路全 PASS 后**：接 NPU 真结果进 Phase 2 UI，完成与主系统的结合。
