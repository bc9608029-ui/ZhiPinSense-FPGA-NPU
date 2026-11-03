# Phase 3 上板指南 — USB 触摸检测 / 校准 / 页面切换（门 5）

> 状态：`READY-FOR-HARDWARE-TEST`，待你本人实测。位流与 1B 相同（v2 双缓冲），只换 PS 程序。

## 硬件前提（已确认）

显示器为 **7" IPS 触摸屏（原生 1024×600，HDMI 输入 720p 自动缩放）**，触摸是 **USB HID**：
- 屏的 **HDMI 口** 接板子 PL 侧 pHDMI；屏的 **touch 口** 用 USB 线接板子 USB host 口——**同一根线同时供电+触摸**。
- **不要按屏的 POWER 键**（USB 上电即自动开机，按 POWER=关机）；供电不稳再单独接 POWER 口。

USB HID 触摸控制器可能上报**单点**（`ABS_X/Y + BTN_TOUCH`）或**多点协议 B**（`ABS_MT_POSITION_X/Y + ABS_MT_TRACKING_ID`）；
程序两者都处理，触摸设备通过**枚举 `/dev/input/event*`** 自动发现（不硬编码 event 编号）。若找不到触摸设备，打印 `PHASE3_TOUCH_FAIL` 并**非零退出（不假 PASS、不自动翻页）**。

## 位流

同 1B（共用 v2，SHA-256 见 `docs/BUILD_RESULTS.md`）。

## 运行

```
cd /tmp/hdmi_v2_sw
./build_on_board.sh run phase3 30           # 检测并标定触摸，等待点击翻页（Ctrl-C 停）
```

## 期望输出

先打印 USB 拓扑（`/proc/bus/usb/devices`）与 input 设备列表（`/proc/bus/input/devices`），然后：
- 找到触摸：`TOUCH_FOUND path=/dev/input/eventX X=[..] Y=[..]` → 打印标定公式 → `PHASE3_PS_READY`，等待触摸；
- 找不到触摸：`PHASE3_TOUCH_FAIL: no touch device found ...` → **非零退出（不假 PASS、不自动翻页）**。

**手势（有触摸）**：点底部 80px 标签栏 = 选页 1/2/3（`hit-region=tabN`）；点其余区域 = 下一页（`hit-region=next-page`）。
第一次成功点击打印 `PHASE3_TOUCH_PASS`。
**画面**：整屏主题色 + 居中大数字（1/2/3）+ 底部三标签（活动标签高亮），翻页时三者同时变化。

## 判据

**PASS**：`TOUCH_FOUND` + 标定公式打印清楚；至少一次点击成功走通「点击→坐标→命中区域→翻页」并打印 `PHASE3_TOUCH_PASS`；
页面数字/颜色/图案正确、无撕裂。
**FAIL**：`PHASE3_TOUCH_FAIL`（找不到触摸设备，非零退出）；或点击后页面切换撕裂/错乱。
> 若 `PHASE3_TOUCH_FAIL`：先查 touch 口 USB 线是否插到板子 USB host、屏是否亮（USB 供电）；
> 再 `dmesg | grep -i -E 'usb|input|hid'` 与 `ls /dev/input/event*`，修好接线后重跑。

## 日志采集

stdout 存 `phase3.log`（务必包含 USB 拓扑 + 检测结论 + 每次翻页/点击行）；屏幕录像。
