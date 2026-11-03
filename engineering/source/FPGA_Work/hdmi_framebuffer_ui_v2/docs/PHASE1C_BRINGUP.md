# Phase 1C 上板指南 — 动态图案 + ≥10 分钟稳定性（门 3）

> 状态：`READY-FOR-HARDWARE-TEST`，待你本人实测。位流与 1B 相同（v2 双缓冲），只换 PS 程序。

## 位流

同 1B（共用 v2 `hdmi_framebuffer_720p_top_disable_icap.bit`，SHA-256 见 `docs/BUILD_RESULTS.md`）。
若刚做完 1B 且位流仍在（未断电），可跳过重新加载。

## 运行

```
cd /tmp/hdmi_v2_sw
./build_on_board.sh run phase1c 600 60      # 默认 600s 自动停；0 = Ctrl-C 停
RUN_TIMEOUT=660 ./build_on_board.sh run phase1c 0 60   # timeout --kill-after=5s 兜底防卡死
```

## 期望输出（逐行）

```
PHASE1C_PS_READY ...
[1C-PS] frame=0    elapsed_s=0   pattern=0  front=1  anomalies=0
[1C-PS] frame=60   elapsed_s=1   pattern=0  ...      anomalies=0
...（elapsed_s 单调增长，anomalies 保持 0）
PHASE1C_PS_PASS (>=600 s, 0 register/readback anomalies)   # 跑满 10 分钟且 0 异常才打印
```

图案每 ~3 秒轮换：移动竖条 → 滚动棋盘 → 垂直渐变 → 纯色。

## 判据

**PASS**：`PHASE1C_PS_PASS` 打印（≥10 分钟 + `anomalies==0`）+ 4 图案持续轮换无撕裂/闪烁/冻屏；
心跳 `frame`/`elapsed_s` 单调无卡死；led[1] 全程慢闪。
**FAIL**：任一时刻画面冻住/花屏、心跳停更、报错，或 `anomalies>0`（打印 `PHASE1C_PS_FAIL`）。

## 日志采集

stdout 存 `phase1c.log`（必须保留到 `PHASE1C_PS_PASS` 或停止行）；屏幕录像 ≥10 分钟段。
