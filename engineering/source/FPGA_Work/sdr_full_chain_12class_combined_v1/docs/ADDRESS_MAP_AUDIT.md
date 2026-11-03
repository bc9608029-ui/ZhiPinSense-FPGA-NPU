# 地址图审计（任务 39e5 最终阶段 §四.8）

> 结论：**两个工程的 `ps_ai.bd` 逐字节一致（SHA256 `78f5599b…`），地址图完全相同，**
> **且 NPU（0x40000000）与 HDMI frame_ctrl（0x40080000）是两段互不重叠的 512K 窗口，**
> **可在同一合并位流中共存，无地址冲突。**

## 1. 权威地址图（来自 `ps_ai.bd` 的 `processing_system7_0/Data` 段，两工程一致）

| 段名 | 地址块 | 偏移 | 大小 | 语义 |
|---|---|---|---|---|
| `SEG_BYolo_GP0_Reg` | `/BYolo_GP0/Reg` | `0x40000000` | 512K | NPU AI_GP 控制总线（iCraft URL `npu=0x40000000`） |
| `SEG_BYolo_GP1_Reg` | `/BYolo_GP1/Reg` | `0x80000000` | 512K | NPU AI_HP DMA 数据总线（iCraft URL `dma=0x80000000`） |
| `SEG_User_GP0_Reg` | `/User_GP0/Reg` | `0x40080000` | 512K | PL 控制寄存器（HDMI 工程里接到 `frame_ctrl`） |
| `SEG_User_GP1_Reg` | `/User_GP1/Reg` | `0x80080000` | 512K | PL 第二控制寄存器 |

各 512K 窗口实际覆盖区间：

| 窗口 | 覆盖 | 
|---|---|
| `0x40000000` | `0x40000000 .. 0x4007FFFF` |
| `0x40080000` | `0x40080000 .. 0x400FFFFF` |
| `0x80000000` | `0x80000000 .. 0x8007FFFF` |
| `0x80080000` | `0x80080000 .. 0x800FFFFF` |

四段两两不重叠（`0x40080000` 不是 `0x40000000` 的 1MiB 窗口内的子区间）。

## 2. 各段在两工程里的接线差异（地址段相同，仅"谁连到它"不同）

| 段 | NPU 工程（ai7030_edif_top + ps_ai_peripheral） | HDMI 工程（hdmi_framebuffer_720p_top） |
|---|---|---|
| `BYolo_GP0`（0x40000000） | 接 `ps_ai_peripheral` 内 AI_Mate 的 AXI-Lite 控制口 | 在 `ps_ai_wrapper` 里 tie-off（`pl_ra_*` 接 0） |
| `BYolo_GP1`（0x80000000） | 接 AI_Mate 的 CustomOp 数据口 → MIG PL-DDR | tie-off |
| `User_GP0`（0x40080000） | tie-off（烟测版未用） | 经 `axi3_to_axilite_bridge` → `frame_ctrl` |
| `User_GP1`（0x80080000） | tie-off | tie-off |
| `S_AXI_HP2_1` | tie-off | 接 `fb_read_720p`（读 PS DDR 帧缓冲） |

关键点：**`ps_ai.bd` 本身同时提供 NPU 的 AI 口（0x40000000/0x80000000）和 PL 控制口（0x40080000/0x80080000）**；
两个工程只是各取所需子集。合并位流只需把两路子集同时接上，地址无需重规划。

## 3. 纠正此前（ui_v1）的错误结论

`ui_v1/docs/BITSTREAM_COMPAT_AUDIT.md` 第 5 节曾写：

> “`frame_ctrl@0x40080000` 落在 `npu=0x40000000` 的 1 MiB 窗口内 … 二者互斥”。

该结论**基于错误假设**：它只看到 iCraft URL `npu=0x40000000` 而没有尺寸信息，保守假设窗口为 1MiB。
本审计以 `ps_ai.bd` 的权威地址段为准：NPU 窗口是 **512K**（`0x40000000..0x4007FFFF`），
`0x40080000` 是独立的 `User_GP0` 段，二者**不重叠、不互斥**。

因此 "NPU 与 HDMI 互斥、需另造合并位流才可同存" 的**方向**是对的：真实原因是**原先尚无
同时实例化 NPU 和 HDMI 的位流**，且**旧位流不具备完整链路能力**；但 "地址冲突" 这个
**具体理由**不成立。合并的障碍不是地址，而是 RTL 集成（见
`COMBINED_FEASIBILITY_AUDIT.md` 的最小合并方案）。

## 4. 合并后的地址图（不变）

合并位流沿用同一 `ps_ai.bd` 地址图：

| 用途 | 基址 | 大小 |
|---|---|---|
| NPU 控制（iCraft `npu=`） | `0x40000000` | 512K |
| NPU DMA（iCraft `dma=`） | `0x80000000` | 512K |
| HDMI frame_ctrl（版本/缓冲/帧基址） | `0x40080000` | 512K（实际用 `0x0C/0x50/0x54` 三寄存器） |
| （预留 User_GP1） | `0x80080000` | 512K |

软件侧 `0x40080000+0x0C == 0x20230218` 版本校验、`axi://zg330aiu?npu=0x40000000&dma=0x80000000`
设备 URL 在合并位流下**原样可用，无需改动**。
