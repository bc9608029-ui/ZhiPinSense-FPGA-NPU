# 位流 / 寄存器兼容性审计（任务 39e5 §八）

> 结论先行：**Gate 8 → Socket → 屏幕回放 兼容，可上板演示；**
> **Gate 9 → Socket → 屏幕（真 NPU 实时分类）在当前位流下 BLOCKED。**
> 本任务不修改任何 RTL / XDC / 位流；解禁依赖 FPGA 侧集成出
> **NPU + HDMI 合并位流**（另立任务，不在本任务范围）。

## 1. 板上存在两套互斥的硬件通路

| 通路 | 基址 / 设备 | 所属位流 | 用途 |
|---|---|---|---|
| HDMI 帧缓冲 | `frame_ctrl@0x40080000`（AXI-Lite）+ `/dev/udmabuf0` | **HDMI-only 位流** | 1280×720 RGB565 双缓冲显示 |
| NPU | `axi://zg330aiu?npu=0x40000000&dma=0x80000000` | **NPU 位流** | ZG330 十二类推理 |

## 2. HDMI 帧缓冲寄存器契约（DirectFramebufferBackend）

来源：`ui_sw/direct_framebuffer_backend.hpp`（本工程拷贝自 `hdmi_framebuffer_ui_v5_visual/sw`）。

| 寄存器 | 偏移 | 语义 | 冻结值 |
|---|---|---|---|
| `slv_reg3`（版本） | `0x0C` | 帧缓冲核版本，写前必读校验 | `0x20230218` |
| `slv_reg20`（缓冲选择） | `0x50` | 乒乓缓冲 bit0（0/1） | 0 或 1 |
| `slv_reg21`（帧基址） | `0x54` | `framebuffer_base >> 3` | 运行时读 sysfs |

- `frame_ctrl_base = 0x40080000`；`version_offset = 0x0C`；`expected_version = 0x20230218`。
- 帧缓冲**物理地址运行时读** `/sys/class/u-dma-buf/udmabuf0/phys_addr`（**绝不硬编码**）。
- `submit_frame()` 是**唯一设备写路径**（标量 volatile 16-bit store，`DFB_SCALAR_STORE_ONLY`）；
  每次写寄存器都读回校验；版本校验**通过后才允许写**，否则立即退出（UI 启动修正 3）。

## 3. NPU 器件 URL

来源：`board_package/npu_classifier.hpp`（iCraft-only，仅板上编译）。

```
kNpuDeviceUrl = "axi://zg330aiu?npu=0x40000000&dma=0x80000000"
```

## 4. 证据：HDMI-only 位流没有 NPU（原文引用）

- `hdmi_framebuffer_ui_v4_fix/docs/HDMI_WORK_REPORT.md`：
  > “去掉 iCraft `Device::Open`（安全显示后端）：**HDMI-only 位流没有 NPU**，
  > 旧 `Device::Open("axi://...?npu=...&dma=...")` 会**卡死板子 Linux**。”

- `hdmi_framebuffer_ui_v4_fix/docs/MASTER_MANUAL.md`：
  > “程序**不再用 iCraft `Device::Open` / NPU 寄存器**（HDMI-only 位流没有 NPU）。”

- `hdmi_framebuffer_ui_v4_fix/docs/BUILD_RESULTS.md`：
  > “相机写侧与 NPU 侧全部 tie-off。”

- 权威上板位流：`hdmi_framebuffer_720p_top_disable_icap.bit`（SHA `df8a0c66…`，5,980,619 B，
  器件 JFMQL30TAI676H，FMSH IP patch 53180205）。

## 5. 地址窗口观察（佐证互斥）

`frame_ctrl@0x40080000` 落在 `npu=0x40000000` 的 1 MiB 窗口内（`0x40000000..0x400FFFFF`）。
即 HDMI 帧缓冲控制页与 NPU 占用**同一段 AXI 地址空间**，二者不可能由两个位流
各自独占同一地址而不冲突 → 它们是**互斥的独立位流**，无法在单板单位流下并存。

## 6. 结论

| 链路 | 需要位流 | 与 UI 服务端同跑 | 判定 |
|---|---|---|---|
| **Gate 8 → Socket → 屏幕回放** | HDMI-only | 是（Gate 8 读 `expected_logits.tsv` 构造 JSONL，**不需要 NPU**） | **兼容，可上板演示** |
| **Gate 9 → Socket → 屏幕（真 NPU 实时）** | NPU | 否（Gate 9 需 NPU 位流、UI 服务端需 HDMI 位流，互斥） | **BLOCKED** |

**BLOCKED 判定的含义**：`run_gate9_ui.sh` 必须 fail-closed —— 在无已验证
NPU+HDMI 合并位流标识符时输出 `FULL_CHAIN_UI_BLOCKED bitstream_incompatible` 并返回非零，
**绝不假装 LIVE**。可提供“记录 JSONL 后切换 HDMI 位流再回放”的演示模式，但必须标
`OFFLINE_REPLAY`，不得称 LIVE。

## 7. 解禁条件（不在本任务范围）

- 需要 FPGA 侧集成的 **NPU + HDMI 合并位流**（同时含 `0x40000000` NPU 与
  `0x40080000` frame_ctrl，地址不冲突、双 IP 均接好 AXI）。
- 合并位流需经 Vivado 构建 + DRC + 上板验证后，给出**新的位流标识符**，才可
  更新本审计把 Gate 9→屏幕 从 BLOCKED 改为可测。
- 本工程（`sdr_full_chain_12class_ui_v1`）**不改 RTL / XDC / 位流**；软件侧已按
  合并位流可无缝接入的方式实现（socket 服务端 + 版本门 + 双缓冲）。
