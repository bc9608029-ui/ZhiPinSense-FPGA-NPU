# 触摸板端测试（任务 39e5 Gate C7，smoke_v2 软件交付）

> 状态：**READY-FOR-TOUCH-HARDWARE-TEST**（离线软件已完成并通过主机测试；未经实机验证绝不写 PASS）。
> **我禁碰板、禁写 Flash；以下所有上板命令由用户本人执行。**
> 最终态只在 C1–C7 全部实测通过后标 **`FULL_CHAIN_WITH_TOUCH_HARDWARE_PASS`**。

## 0. 前提

- 已加载合并位流 `outputs/smoke_v1/bitstream/combined_npu_hdmi_disable_icap.bit`
  （5,980,628 B，SHA256 `22fec95c…`，仅 JTAG 临时加载，**绝不写 Flash**）。
- 已解包本软件包，`sha256sum -c SHA256SUMS.txt` 全 OK。
- 触摸控制器已通过 USB 接入（VID `1a86` PID `e5e3`，USB2IIC_CTP_CONTROL）。
- 以 root 运行（UI 服务端需 `/dev/mem` + `/dev/udmabuf0`；evdev 需读 `/dev/input`）。

## 1. 构建

```sh
./board_package/build_ui_live.sh g++      # 期望 UI_BUILD_RESULT result=PASS
```

非零退出即停（fail-fast）。

## 2. 起 UI 服务端并核对触摸发现

```sh
./scripts/run_ui_live.sh
# 期望： UI_LIVE_READY sock=/run/sdr_amr_ui.sock pid=<pid> log=/tmp/sdr_ui_live/ui_live.log
tail -f /tmp/sdr_ui_live/ui_live.log
```

- 必须看到 `UI_VERSION_CHECK ... ok=YES`（frame_ctrl 版本 `0x20230218`）才会碰 framebuffer。
- 触摸**按 VID/PID 发现**（读 `/sys/class/input/eventN/device/id/vendor|product`），
  **不写死 `/dev/input/eventN`**（USB 枚举顺序会漂移）。
- 启动行三选一：
  - `UI_TOUCH status=CONNECTED device=/dev/input/eventN vid_pid=1a86:e5e3` —— 正常；
  - `UI_TOUCH status=DISCONNECTED` —— 触摸未接/枚举未就绪（服务端**不退出**，仅 Touch 页显示 DISCONNECTED）；
  - `UI_TOUCH status=DISABLED` —— 显式传了 `--no-touch`。
- 首屏应显示 MAIN 页（STALE 等待帧 + 底部 MAIN/DIAGNOSTICS/TOUCH 三导航）。

## 3. 三页导航 + 触摸命中（核心功能）

底部导航命中带为 `y ∈ [630, 719]`（原始 1280×720；面板缩放后仍 ≥60px 物理高度），
三等分：MAIN（左）/ DIAGNOSTICS（中）/ TOUCH（右）。

1. 点 **TOUCH**（右侧三分之一）→ 屏幕切到 TOUCH 页，显示：
   `device / vendor / axis X / axis Y / mapping X / mapping Y` 与右侧
   `touch: CONNECTED`、`taps 1`、`last (x, y)`（随按压更新）。
2. 点 **DIAGNOSTICS**（中间）→ 切到 DIAGNOSTICS 页。
3. 点 **MAIN**（左侧）→ 切回 MAIN 页。
4. 快速连点两次同一 tab：**debounce 折叠**（第二次不切页、`taps` 不增加）；
   间隔 >400ms 的第二次点击才计入。

通过门：三页都能来回切换；`taps` 计数与实际有效点击一致；`last (x, y)` 落在
屏幕坐标内（`x∈[0,1279]`、`y∈[0,719]`，绝不出界）。

## 4. 坐标映射核对（swap / invert / clip）

若触摸方向与屏幕不符，用 CLI 覆盖（`run_ui_live.sh` 会把参数透传给服务端）：

```sh
./scripts/run_ui_live.sh --touch-swap-xy            # X/Y 互换
./scripts/run_ui_live.sh --touch-invert-x --touch-invert-y   # 单轴翻转
./scripts/run_ui_live.sh --touch-debounce-ms=600    # 调整 debounce
./scripts/run_ui_live.sh --touch-vendor=1a86 --touch-product=e5e3   # 覆盖 VID/PID（十六进制）
```

- 设备 ABS_X / ABS_Y 量程经 `EVIOCGABS` 读取，Touch 页 `axis X / axis Y` 显示实际量程；
  `mapping X / mapping Y` 显示 `(raw_*) -> 1280px / 720px`（+ `(inv)` 标记翻转）。
- 原始值无论是否越界都被 **clip** 到 `[0, screen-1]`，绝不可能落点出界。
- 量程退化（`max<=min`）时该轴失效 → 不产生触摸点，服务端不崩溃。

## 5. 拔插恢复（fail-soft，绝不退出）

1. 拔掉触摸 USB 线 → 服务端**必须继续运行**（`kill -0 <pid>` 仍活、socket 仍在、
   `UI_STATS` 持续打印）；Touch 页变 `touch: DISCONNECTED`，日志出现
   `UI_TOUCH status=DISCONNECTED`。
2. 重新插入 → 服务端自动重枚举（≤1s 周期），日志出现
   `UI_TOUCH status=RECONNECTED device=/dev/input/eventN`，触摸恢复可用。

通过门：拔插全程 UI 不退出、不卡死、不残留假 CONNECTED。

## 6. 触摸不得影响分类 / 发射 / 射频路径（安全红线）

- 触摸**只**切换显示页，绝不改十二类契约、分类结果、TX 功率或 RF 路径
  （`touch_evdev.hpp` / `touch_geometry.hpp` 只开 evdev 设备，从不碰 NPU / Pluto / `/dev/mem` 写）。
- 验证：在 Gate 9 屏幕实时显示期间来回点三页，`UI_STATS` 的
  `received/valid/rendered` 与显示 top-1 类**不变**；Gate 9 日志的
  `tx_atten` / `rx_gain` / 定标值**不被触摸改动**。

## 7. 30 分钟稳定性 + USB 并发

```sh
./scripts/run_ui_live.sh
# 连续运行 ≥30 分钟，期间：
#   * 每 5 分钟点一轮三页；* 中途拔插触摸 2 次；* 观察无 SIGBUS / 无崩溃 / 无卡死。
```

通过门：30 分钟不退出；`UI_STATS` 持续输出；拔插后 `UI_TOUCH status=RECONNECTED` 每次都恢复；
（若同时做 USB 其他外设热插拔）系统与 UI 均不因此失稳。

## 8. 收口与收工

```sh
./scripts/stop_ui_live.sh          # 期望 UI_LIVE_STOPPED pid=<pid>（仅 kill -TERM，不 pkill）
sync && poweroff
```

## 判定红线

- 离线软件最高只标 **READY-FOR-TOUCH-HARDWARE-TEST**；只有用户上板全 PASS 才标
  `FULL_CHAIN_WITH_TOUCH_HARDWARE_PASS`（C1–C7）。
- 触摸路径**只**开 evdev，绝不写 NPU / Flash / `/dev/udmabuf0` 之外的设备寄存器。
- 我禁碰板 / 禁写 Flash；JTAG 只加载合并位流，**绝不写 Flash**。
