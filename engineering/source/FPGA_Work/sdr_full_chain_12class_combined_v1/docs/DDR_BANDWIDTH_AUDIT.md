# DDR 区域 / 带宽审计（任务 39e5 最终阶段 §四.11）

> 结论：**两条 DDR 独立、互不争抢**——PS DDR（32-bit）承载 Linux + 帧缓冲，PL DDR（64-bit MIG）
> 承载 NPU DMA。帧缓冲读带宽极小（~110 MB/s@60Hz），对 PS DDR 无压力，无带宽阻塞。

## 1. DDR 区域划分

| DDR | 位宽 | 位置 | 用途 |
|---|---|---|---|
| PS DDR（`DDR_0_*`） | 32-bit | 两工程都有（PS7 控制器，`MT41K256M16 RE-125`） | Linux + 帧缓冲（`/dev/udmabuf0` CMA）+ 触摸/USB |
| PL DDR（`ddr3_*`） | 64-bit | 仅 NPU 工程（MIG `mig_7series_0`） | NPU DMA 数据（权重/激活，`dma=0x80000000`） |

- NPU 工程 `ps_ai_peripheral` 端口表同时含 `DDR_0_*`（PS DDR）与 `ddr3_*`（PL DDR），已双 DDR 并存。
- HDMI 工程 `hdmi_framebuffer_720p_top` 仅含 `DDR_*`（PS DDR），**无 MIG/PL-DDR**。

## 2. 帧缓冲读带宽（HDMI 侧）

- 分辨率 1280×720，RGB565 = 2 B/像素 → 单帧 1,843,200 B ≈ 1.76 MB。
- @60Hz 读带宽 ≈ 110 MB/s；@30Hz ≈ 55 MB/s（软件双缓冲 + 显示 tick 实际 ≤60Hz）。
- 走 `S_AXI_HP2_1`（64-bit）读 PS DDR。PS DDR（32-bit @ ~533MHz DDR3）理论带宽 GB/s 级，
  帧缓冲读仅占个位数百分比，**无压力**。

## 3. NPU DMA 带宽（NPU 侧）

- NPU DMA 走 PL DDR（64-bit MIG），与帧缓冲读（PS DDR）**不同 DDR，物理隔离，互不影响**。
- 十二类推理 ~1.14ms/帧（1×2×1024 输入），数据量小，PL DDR 带宽充裕。

## 4. 合并后的带宽图

| 通路 | DDR | 方向 | 带宽 |
|---|---|---|---|
| 软件写帧缓冲（submit_frame → udmabuf0） | PS DDR | CPU 写 | ~百 MB/s 级（非连续，按需） |
| fb_read_720p 读帧缓冲 | PS DDR | HP2_1 读 | ~55–110 MB/s |
| NPU DMA | PL DDR | MIG 读/写 | 推理 ~1.14ms/帧，带宽小 |

NPU 与 HDMI 帧缓冲**不共享同一条 DDR**，故不存在"争带宽导致推理慢或显示断帧"的风险。

## 5. 结论

DDR 区域清晰、带宽充裕，**无 DDR 带宽阻塞**。合并位流沿用 NPU 工程的双 DDR 拓扑（PS DDR + PL DDR），
只需把帧缓冲读通路（`fb_read_720p` → `S_AXI_HP2_1`）接入 PS DDR 侧。
