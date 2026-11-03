# Phase 2 上板指南 — 完整识别 UI 离屏 RGB565 渲染（门 4）

> 状态：`READY-FOR-HARDWARE-TEST`，待你本人实测。位流与 1B 相同（v2 双缓冲），只换 PS 程序。

## 位流

同 1B（共用 v2，SHA-256 见 `docs/BUILD_RESULTS.md`）。

## 类列表（重要）

`phase2_ui_render.cpp` 里 `CLASS_NAMES` 为**最终十类顺序**（2026-10-04 定稿）：
`AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM`。
渲染器是**通用 N 类**：布局随 `CLASS_NAMES` 自适应，**不改位流/其它代码**。模拟置信度已归一化（softmax，sum=100%）。

## 运行

```
cd /tmp/hdmi_v2_sw
./build_on_board.sh run phase2 -1 20        # Top-1 每 2s 轮换（动态）
./build_on_board.sh run phase2 0 20         # 固定 Top-1 = AM-DSB（静态截图用）
```

## 期望画面

- 顶部标题栏：`RF SIGNAL RECOGNITION`
- 状态行：`SNR: ... dB   TOP-1: ...   CONF: ...%   LAT: ...ms   FRAME: ...`
- 中部 10 行：序号 + 类名 + 置信度条（按百分比填充）+ 百分比
- 底部：`RESULT > <Top-1 类名>` 高亮

## 判据

**PASS**：`PHASE2_UI_PASS` 打印（软件门）+ 标题/状态/10 类名文字清晰可读；Top-1 与置信度条动画无撕裂；
百分比与类名对应正确（置信度 sum=100%，Top-1 由 argmax 推出、状态行/高亮/结果框一致）。
**FAIL**：文字缺失/错位、花屏、撕裂、冻屏。

## 日志采集

stdout 存 `phase2.log`；屏幕照片（动态一张 + 静态 `run phase2 0 20` 一张）；`_disable_icap.bit` 的 `sha256sum`。
