# Phase 1B 上板指南 — DDR 双缓冲动态测试（门 2）

> 状态：`READY-FOR-HARDWARE-TEST`，待你本人实测。我不碰板、不写 Flash。
> 完整接线/JTAG/回滚见 `MASTER_MANUAL.md`，本文只列 1B 专属内容。

## 位流

| 项 | 值 |
|---|---|
| 加载文件 | `fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top_disable_icap.bit` |
| SHA-256 | 见 `docs/BUILD_RESULTS.md`（加载前 `sha256sum -c`） |
| 加载脚本 | `fpga/program_phase1b_jtag.tcl`（Vivado 2020.2） |
| RTL 变更 | `fb_read_720p.sv` 把 `read_addr_1 = camera_rd_addr + 230400`、`read_addr_index = {1'b0, 同步后的 camera_wr_addr[0]}`（1-bit 双触发同步） |

## 前置

1. v2 位流已按 MASTER_MANUAL 步骤 2 加载：led[0]（J1）常亮、led[1]（M6）慢闪。
2. 板上 Linux 可登录，且 u-dma-buf 已加载（`/dev/udmabuf0` 存在、`cat /sys/class/u-dma-buf/udmabuf0/phys_addr` 有值）。**无需 iCraft**。

## 运行

```
scp -r sw <board>:/tmp/hdmi_v2_sw/ && ssh <board>
cd /tmp/hdmi_v2_sw
./build_on_board.sh                 # CMake；失败则 ./build_on_board.sh g++（无需 iCraft，仅 libc）
./build_on_board.sh run phase1b 0 60
```

## 期望输出（逐行）

```
[DFB] frame_ctrl version = 0x20230218 (expect 0x20230218)
[DFB] udmabuf phys=0x... size=... frame_bytes=... total=...
[1B-PS] FB0=0x... FB1=0x... rd(0x54)=0x...   (8 字节对齐、fb>>3 在 27 位内)
PHASE1B_PS_PASS (version/alignment/capacity/readback OK)
[1B-PS] frame=0 front=1               (每秒一行，front 在 0/1 间切换)
```

## 判据

**PASS**（全满足）：`PHASE1B_PS_PASS`（版本/对齐/容量/读回全过，软件门）+ HDMI 显示深底白竖条**平滑移动**；
观察 ≥1 分钟**无撕裂**（竖条无水平断裂）；led 全程正常。
**FAIL**：任一条 `[DFB] FAIL` / `FAIL`；竖条撕裂/错位；冻屏。

## 日志采集

程序 stdout 存 `phase1b.log`；屏幕录像 ≥1 分钟；JTAG 输出；`_disable_icap.bit` 的 `sha256sum`。
