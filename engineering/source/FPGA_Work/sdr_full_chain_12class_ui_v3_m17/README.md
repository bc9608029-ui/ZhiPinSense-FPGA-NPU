# sdr_full_chain_12class_ui_v3 — 十二类 SDR 智能识别系统 · UI v3 增量（参数测量 + 工作模式 + 真实 RF 验证）

> **离线状态：`READY-FOR-M17-GATE10-UI-INTEGRITY-AND-TOUCH-HARDWARE-TEST`**
> （未经实机验证，**绝不**标 PASS / READY；我禁碰板 / 禁写 Flash，上板由用户本人执行。）

## 本工程做什么

在冻结的十二类实时链路（NPU 分类 + HDMI 实体屏幕）之上做**软件/DSP/板端程序的 UI v3 增量**，
补齐三页 UI 的「参数测量 + 工作模式 + 真实 RF 验证」，并让 **Gate 9 成为真正的实时生产者**：

```
Pluto SDR → RX IQ → NCO/重采样/receiver_scale → 预处理(张量 [1,2,1024])
         → 十二类 NPU → Gate 9 生产者（DspMeasure + SignalPresence + WorkModeEngine
                         + BAND SCAN LO 扫频 + 模型标量/RF 增益真实作用于输入）
         → ResultFrame v3 (12class-chain-v2, 含 measurements/presence/level_mode/
                         model_scale/rf_gain_db/work_mode/run_state)
         → Unix Socket → HDMI 三页 UI（CLASSIFY / PARAMETERS / MODE）  ↕ TOUCH
         ↕ 反向控制通道（Gate 9 生产者唯一持有：SET_MODE / START / STOP / STATUS）
```

- **必须真实并发与真实测量**，禁止用 Golden/Mock/离线回放冒充实时、禁止把纯逻辑单测写成
  板端功能已完成。
- 保护原工程**绝不修改**：源基线 `sdr_full_chain_12class_combined_v1` 冻结只读。

## 里程碑（M0–M16）

| 里程碑 | 内容 |
|---|---|
| M0 | 波形/训练信号契约审计（冻结类别序 + 波形规则） |
| M1 | 无信号判定 `SignalPresence`（非 `SIGNAL_PRESENT` 不发布分类） |
| M2 | 自动幅度 `AutoLevelControl`（慢/有界数字标量 + RF/ADC 增益） |
| M3 | 轻量 DSP 参数测量 `DspMeasure` / `FrameMeasurements` |
| M4 | `ResultFrame` v3（`12class-chain-v2`）+ `result_frame_v3_line` + 解析 |
| M5 | 三页 UI（CLASSIFY/PARAMETERS/MODE）+ `ui_state_map` |
| M6 | 反向控制通道 `mode_control` + `board_mode_ctl` + `unix_socket_server.reply` |
| M7/M8 | `WorkModeEngine`（FIXED 恒等 + AUTO LOCK 类稳定锁） |
| M9 | Gate 10 十二类真实 RF 自测（波形合成 + Pluto TX/RX 回环） |
| M10 | BAND SCAN LO 扫频时序 `BandScanSequencer` |
| M11 | 开源参数模型审计（只读） |
| M12 | 自主启动可行性审计（只读） |
| M13 | 确定性打包（`GZIP=-n` + `--mtime` + numeric-owner） |
| **M14** | **生产者集成**：`producer_12class.hpp` + Gate 9 连续生产者循环真正接线（见下） |
| **M15** | **统一补丁**：Gate 10 顺序自测 + HDMI 脏帧/撕裂 + 控制通道实时响应 + 64QAM 精度诊断 + 无信号集成（见下） |
| **M16** | **第三页实体触摸模式控制**：FIXED / AUTO_LOCK / BAND_SCAN / START / STOP 触摸直控，UI 为纯控制客户端（见下） |
| **M17** | **Gate 10 采样回归 + 生命周期 + HDMI 撕裂 + UI 空闲优化最终任务书**：settle 路径删除、TX/RX 缓冲生命周期平衡、事件驱动翻转、启动消隐、dump 富化（见下） |

## M14 生产者集成（本工程当前增量）

把原「UI 控制 socket 只改 UI 内部显示态、PARAMETERS 页只有占位、BAND SCAN 只有纯逻辑」的
缺陷一次性修正：

1. **Gate 9 真正计算 `FrameMeasurements`**：每帧 `DspMeasure::measure`，PARAMETERS 页显示真实值。
2. **接线 `SignalPresence`**：非 `SIGNAL_PRESENT` 的帧 `publish=false`、不产有效分类。
3. **接线 `WorkModeEngine`**：FIXED/AUTO_LOCK/BAND_SCAN 的幅度管理与发布策略真实生效；
   `model_scale` 真实作用于预处理输入（缩放后再喂 NPU），RF 增益有界/可记录。
4. **控制权威在生产者侧**：`board_gate9_full_chain_12class --ctl-sock` 唯一持有控制通道，
   UI 只显示生产者回传的权威 `work_mode`/`run_state`，绝不本地自改冒充模式生效。
5. **Gate 9 输出 `result_frame_v3_line`**：含 `measurements/presence_state/level_mode/
   model_scale/rf_gain_db` 与真实 `work_mode`/`run_state`。
6. **BAND SCAN 真实执行**：`set_rx_lo` 按 start/stop/step/dwell 扫频、每步清类锁、逐帧回报
   LO/进度。
7. **Gate 10 明确为独立自测**：产 §八 `12class-chain-v1` 记录，不产 v2、不喂 MODE/PARAMETERS 页。

新增/改动文件（SHA 见 `PROVENANCE.md` §3 M14 与打包内 `SHA256SUMS.txt`）：
`board_package/producer_12class.hpp`、`board_package/board_gate9_full_chain_12class.cpp`、
`board_package/board_ui_live_12class.cpp`、`board_package/board_mode_ctl.cpp`、
`board_package/board_gate10_selftest_12class.cpp`、`host_tests/test_producer_12class.cpp`、
`host_tests/test_result_frame_v3.cpp`、`host_tests/test_ui_v3_pages.cpp`、
`host_tests/build_host_tests.sh`、`host_tests/run_tests.sh`、`scripts/stop_ui_live.sh`、
`scripts/mode_ctl.sh`、`docs/MODE_CONTROL_CONTRACT.md` 等。

## M15 统一补丁（本工程当前增量，五子任务）

1. **Task A — Gate 10 顺序 12 类自测**：逐类 `stop+destroy` 旧 TX 缓冲→等待→`create+push`→
   重建 RX 缓冲→丢弃 FIXED settle 帧；`--seed=0x39e50001` 十六进制解析；终门禁 12 类各 20/20、
   总 valid=240、short/overflow/drop/disc=0、single_refill=1、restore=PASS。
2. **Task B — HDMI 脏帧/撕裂**：`--display-diagnostic/--display-static/--display-refresh-hz`；
   启动顺序 get2→清→sync→render→sync→设物理地址→submit→READY；运行时只画非扫描后缓冲。
3. **Task E — 控制通道实时响应 + UI 状态同步**：控制线程非阻塞 poll→线程安全命令队列→唯一
   生产者 12 安全点 apply；ACCEPTED≤500ms/APPLIED≤2s 两阶段；STATUS 报
   requested/applied_mode、requested/applied_running、command_id/control_queue_depth；
   STOP→屏幕 STOPPED、BAND_SCAN 可中断。
4. **新增项1 — 64QAM 精度诊断**：板端 `--dump-error-samples=N --dump-dir=DIR` 落盘误分类帧；
   主机 `host_tools/compare_64qam_threeway.py` 做 ONNX fp32 / `icraft-run --fake_qf` / 板端
   NPU 三方归因（生成参数审计排除波形偏差，归因= int8 量化精度，交棒 V2，不重训）。
5. **新增项2 — 真实无信号集成**：`--phase=ambient` rx-only（`tx_active=0`），连续 RX+DSP+
   SignalPresence+UI，SIGNAL_PRESENT↔NO_SIGNAL 迟滞确认，非 SIGNAL_PRESENT 帧绝不发假分类。

新增/改动文件（SHA 见 `PROVENANCE.md` §3 M15 与打包内 `SHA256SUMS.txt`）：
`board_package/control_channel.hpp`、`board_package/gate9_phase.hpp`、`sdr_adapter/crc32.hpp`、
`board_package/board_gate10_selftest_12class.cpp`、`board_package/board_gate9_full_chain_12class.cpp`、
`board_package/board_ui_live_12class.cpp`、`board_package/mode_control.hpp`、
`board_package/result_frame_v2_parse.hpp`、`board_package/ui_state_map.hpp`、
`sdr_adapter/pluto_device.hpp`、`sdr_adapter/pluto_device_libiio.cpp`、`sdr_adapter/ui_report.hpp`、
`ui_sw/direct_framebuffer_backend.{hpp,cpp}`、`scripts/{run_display_integrity_test.sh,
test_mode_control_runtime.sh,run_no_signal_ambient.sh,run_gate10.sh}`、
`host_tests/{test_control_channel,test_display_integrity,test_gate10_sequential,
test_no_signal_ambient}.cpp`、`host_tools/compare_64qam_threeway.py`、
`docs/64QAM_PRECISION_DIAGNOSIS.md` 等。

## M16 第三页实体触摸模式控制（本工程当前增量）

终端用户直接在**第三页（MODE）实体触摸屏**上控制 `FIXED / AUTO_LOCK / BAND_SCAN /
START / STOP`，无需终端；`mode_ctl.sh` 仅保留为调试接口，不作为验收证据。

架构硬约束：触摸按钮 → `board_ui_live_12class`（控制客户端）→
`/run/sdr_amr_control.sock` → **Gate 9 唯一生产者**（控制线程 ACCEPTED，生产者安全点
APPLIED）→ 回传 ACCEPTED / APPLIED / STATUS → UI 更新实际状态。**UI 绝不直接调
libiio / 切 LO / 改增益 / 控制 Pluto / 操作 NPU**；点击只产生请求，**仅当对应 APPLIED
到达才高亮实际模式**；REJECTED / TIMEOUT 保留原实际模式。

- 第三页：三模式按钮（FIXED/AUTO LOCK/BAND SCAN）+ START/STOP + 六行详情卡
  （current/requested mode、run state、control connection、last command、command status）。
- 触摸规则：同按钮按下+释放=一次点击；长按=一条命令；拖出=取消；命令在途禁重复提交
  （STOP 例外，独立槽）；独立 `control_taps` 计数器。
- 控制客户端：`--ctl-sock`/`--control-timeout-ms=2000`/`--control-reconnect-ms=1000`；
  UI 可在 Gate 9 之前启动、socket 缺失时按钮禁用、≤1 s 自动重连、重连发 STATUS；
  绝不阻塞渲染/触摸、退出只关客户端 fd、**绝不 unlink 生产者 socket**。

新增/改动文件（SHA 见 `PROVENANCE.md` §3 M16 与打包内 `SHA256SUMS.txt`）：
`board_package/control_client.hpp`、`board_package/touch_mode_control.hpp`、
`board_package/board_ui_live_12class.cpp`、`ui_sw/ui_render.{hpp,cpp}`、
`host_tests/test_touch_mode_control.cpp`（86 断言）、`host_tests/{build_host_tests,run_tests}.sh`、
`scripts/test_touch_mode_control.sh`、`docs/TOUCH_MODE_CONTROL_CONTRACT.md` 等。

## M17 Gate 10 采样回归 + 生命周期 + HDMI 撕裂 + UI 空闲优化（本工程当前增量）

修复四类板端缺陷（详见 `docs/M17_HARDWARE_FINDINGS.md` + `docs/FRAMEBUFFER_VBLANK_AUDIT.md`
+ `docs/M17_BOARD_ACCEPTANCE.md`）：

1. **Task A — Gate 10 settle 回归**：删除 M15「捕获 frames+settle 再丢弃前 N 帧」路径
   （它把默认 `--settle-frames=2` 下的 OOK 压成 0/20）；唯一策略 `TIME_ONLY`
   （`--settle-wait-ms` 等待模拟/RF 稳定，不丢帧），官方捕获精确 `required_input(frames)`；
   非零 `--settle-frames` **fail-closed** 拒绝。
2. **Task B — TX/RX 缓冲生命周期**：delta 快照改到 `PlutoTx` RAII 析构 + 类末
   `recreate_rx_buffer` **之后**，每类可证 `tx_create=1/tx_destroy=1/tx_live=0/rx_live=0`。
3. **Task C — dump 富化**：`--dump-error-class`（单目标类或 all）+ 富化 manifest（帧序号/
   CRC32/置信度/模型与位流 SHA）+ `SHA256SUMS` 侧车指纹。
4. **Task D — 帧缓冲 vblank 审计（只读）**：确认翻转选择 `camera_wr_addr[0]` 经 2-FF 同步
   帧起始锁存、无 vblank/ack 寄存器 → 只能软件侧缓解（不改 RTL）。
5. **Task E — HDMI 撕裂/闪烁**：`ui_dirty_state.hpp` `display_changed` + `FlipScheduler`
   事件驱动翻转——内容真实变化才翻转，且受 `min_interval_ms` 下限约束。
6. **Task F — 启动条纹**：`DirectFramebufferBackend::set_display_enable` 写
   `disable_hdmi`（slv_reg30 bit0）；启动顺序改 **消隐 → 清空 → submit 帧 0 → 编程 rd_addr →
   解除消隐**，PL 首次扫描即有效帧。
7. **Task G — UI 空闲 CPU**：同上 `FlipScheduler` + `UI_RUNTIME_STATS`（`submits/skips`），
   静止帧不再每 tick 走渲染→拷贝→msync→翻转整条路径（~32% 空转消除）。
8. **Task H — M16 触摸保全**：M16 触摸模式控制文件 `touch_mode_control.hpp` /
   `control_client.hpp` / `touch_evdev.hpp` / `touch_geometry.hpp` **字节不变**；验收脚本
   `test_touch_mode_control.sh` 使用长运行生产者 `run_gate9_ui.sh --phase=offline`。

64QAM 16/20 属**模型鲁棒性（int8 量化精度）**：只保留诊断证据，**不重训/不调门限/不假修**，
交棒 `ad_amr_12class_robust_v2`。

新增/改动文件（SHA 见 `PROVENANCE.md` §3 M17 与打包内 `SHA256SUMS.txt`）：
`board_package/gate10_settle.hpp`、`board_package/ui_dirty_state.hpp`、
`board_package/board_gate10_selftest_12class.cpp`、`board_package/board_ui_live_12class.cpp`、
`ui_sw/direct_framebuffer_backend.{hpp,cpp}`、`sdr_adapter/sha256.hpp`、
`scripts/{common.sh,run_gate10.sh}`、`host_tests/{test_gate10_settle,test_ui_scheduler,
test_display_integrity}.cpp`、`host_tests/{build_host_tests,run_tests}.sh`、
`docs/{FRAMEBUFFER_VBLANK_AUDIT,M17_HARDWARE_FINDINGS,M17_BOARD_ACCEPTANCE}.md` 等。

## 主机验证（离线侧已全绿）

- 主机测试 `host_tests/run_tests.sh`：**ALL HOST TESTS PASSED**（含 M17 新增
  `test_gate10_settle` 27 断言 + `test_ui_scheduler` 22 断言 + `test_display_integrity` 增至
  59 断言，以及 M14 `test_producer_12class` 48 断言 + M16 `test_touch_mode_control` 86 断言）。
- iCraft 头 `-fsyntax-only`（Gate 7/9/10）：**syntax OK**。
- 全部脚本 `bash -n`：**OK**。
- 板端构建回归 `host_tests/test_board_build.sh`：**24 passed, 0 failed**。

> 上板前这些只是「主机侧逻辑/语法/构建」验证；**真实板端运行仍待用户本人上板复测**。

## 状态红线

- 离线完成最高只标 **`READY-FOR-M17-GATE10-UI-INTEGRITY-AND-TOUCH-HARDWARE-TEST`**。
- 未经用户实机测试，不写 `UI_V3_HARDWARE_PASS / AUTO_LOCK_PASS / BAND_SCAN_PASS /
  12CLASS_RF_PASS / 64QAM_PASS / GATE10_12CLASS_RF_PASS / DISPLAY_INTEGRITY_PASS /
  CONTROL_RUNTIME_PASS / TOUCH_MODE_CONTROL_HARDWARE_PASS /
  GATE10_PASS / SCREEN_PASS / FULL_CHAIN_HARDWARE_PASS / PROJECT_COMPLETE /
  FINAL_MODEL_PASS / OOD_PASS / FULL_SYSTEM_FINAL_PASS`。
- 模型标签 `12CLASS_CHAIN_VALIDATION_MODEL`，OOD=NO_GO。
- 64QAM 16/20（M17 Task A3 诊断）仅归因，**不重训/不换模型/不调门限/不挑种子**；交棒
  `ad_amr_12class_robust_v2`。
- 权威合并位流 `combined_npu_hdmi_disable_icap.bit`（SHA `22fec95c…`）与
  十二类模型 `model_12class.raw`（SHA `2ae95275…`）**保持不变**；本工程不碰 RTL/XDC/位流/Flash。
- 我禁碰板、禁写 Flash；上板由用户本人执行。

## 目录

```
sdr_full_chain_12class_ui_v3/
├── board_package/      ← 板端 C++（Gate 9/10 生产者、UI 服务端、控制客户端、纯逻辑头）
├── sdr_adapter/        ← DSP/测量/信号/幅度/结果帧（header-only 纯逻辑）
├── ui_sw/              ← Style A 三页渲染（font_atlas + ui_render）
├── contracts/          ← 类别/波形契约
├── model_12class/      ← 冻结模型（json/raw/sha256/部署契约）
├── deployment_golden/  ← 离线 Golden 输入 + 期望侧车
├── scripts/            ← 运行/构建/打包/控制脚本（含 mode_ctl.sh、package_board_release_ui_v3.sh）
├── host_tests/         ← 主机测试（x86 WSL，iCraft/libiio-free）
├── host_tools/         ← 主机侧诊断工具（Python，Windows 主机，非板端）
├── docs/               ← 契约与审计（M0–M17）
├── PROVENANCE.md       ← 来源与增量修改登记（§3 M14/M15/M16）
├── SOURCE_PROVENANCE_SHA256.txt
└── dist/               ← 确定性交付包 + SHA256SUMS.txt
```
