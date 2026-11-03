# Phase 2 上板指南 — 仪器化识别 UI（三页，门 4）

> 状态：`READY-FOR-HARDWARE-TEST`，待你本人实测。
> 位流与 v2 双缓冲相同（`_disable_icap.bit`，SHA-256 `686bb1e3…`），只换 PS 程序（v3）。

## 位流

复用 v2 双缓冲位流（`fpga/bitstream/hdmi_framebuffer_720p_top_disable_icap.bit`），
时序 / TMDS / 时钟链 / PS7-DDR3 **冻结不动**。加载前先 `sha256sum -c` 校验。

## 类别契约（重要：不写死 10 类）

UI 渲染器是**运行时 N 类（8–16）**，类别顺序来自 `model_contract.hpp`，**不在 UI 代码里重复写死**：

- 当前板测契约 `model::contract_v1_1()` = **10 类**：
  `AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM`
- 目标模型 `contract_target_12()` = 12 类（OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK/GMSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM）——**仅预留，不冒充真实模型输出**。

当前 `phase2_ui_render.cpp` 用 10 类契约；置信度是 **MOCK 旋转 softmax**（画面已标 `MOCK/DEMO`）。

## 运行

```
cd /tmp/hdmi_v3_sw
./build_on_board.sh                  # CMake；失败则 ./build_on_board.sh g++
./build_on_board.sh run phase2 -1 20 -1    # 动态 Top-1、20 fps、三页轮换
./build_on_board.sh run phase2 7 20 0      # 固定 16QAM、Overview 页（静态截图用）
./build_on_board.sh run phase2 0 20 2      # 固定 AM-DSB、Diagnostics 页
```

参数：`phase2_ui_render [static_top] [fps] [page]`
- `static_top`：`-1` = Top-1 每 ~2s 轮换；`0..9` = 固定类号。
- `fps`：默认 20。
- `page`：`-1` = 三页轮换（每页约 4s）；`0/1/2` = 固定 Overview / All Classes / Diagnostics。

## 期望画面（三页）

顶部标题栏 `RF SIGNAL RECOGNITION`；其下三个标签 `OVERVIEW / ALL CLASSES / DIAGNOSTICS`（活动标签高亮）；右上角 `LIVE`/`MOCK` 徽标。

1. **Overview**：Top-1 类名大号 + 置信度 + 置信度带（High/Medium/Low）+ **Top-5 置信度条**。
2. **All Classes**：副标题 `FIXED CONTRACT ORDER`；按 `class_count` **动态排布** N 行（`%02d` 序号、`>` 标 Top-1、类名、置信度条、百分比）。
3. **Diagnostics**：两列 KV（FB phys、frame_ctrl 版本、front buffer、frame/dropped/out-of-order/duplicate/stale/error 计数、fps、latency）+ 事件日志框。

> 一致性规则：Top-1、状态带、Top-5、All Classes 高亮全部来自**同一份归一化概率向量**（`draw()` 内部 sanitize 一次），天然一致；颜色从不作为唯一状态表达（每个色块都带文字）。

## 判据

**PASS（软件门 + 硬件门）**：
- 软件门：`PHASE2_UI_PASS` 打印（版本门 `0x4008000C==0x20230218` + `0x40080054==phys>>3` + `0x40080050` 写读回一致 + 首帧 staging→标量提交→flush→翻页成功）。
- 硬件门：三页文字清晰可读；Top-1 与置信度条动画**无撕裂**；置信度 sum=100%；Top-1 由 argmax 推出且各页一致。

**FAIL**：文字缺失/错位、花屏、撕裂、冻屏、任一条 `[DFB] FAIL`、或**任何 SIGBUS**。

## 日志采集

stdout 存 `phase2.log`（含 `PHASE2_UI_PASS` + 每帧 `[2-PS] frame=.. page=.. top1=.. conf=..% lat=..ms`）；三页各拍一张静态截图（`run phase2 N 20 0/1/2`）；`_disable_icap.bit` 的 `sha256sum`。
