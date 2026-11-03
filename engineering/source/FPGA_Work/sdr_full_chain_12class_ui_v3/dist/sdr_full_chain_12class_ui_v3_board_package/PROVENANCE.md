# PROVENANCE.md — sdr_full_chain_12class_ui_v3 来源与增量修改记录

> 本工程 = 任务 39e5 **UI v3 增量**（十二类 SDR 智能识别系统：参数测量 + 工作模式 + 真实 RF 验证）。
> 源基线 = `F:\FPGA_Work\sdr_full_chain_12class_combined_v1`（**冻结，只读，绝不修改**）。
> 权威合并位流与模型**保持不变**，本工程只增加软件/DSP/板端程序，不碰 RTL/XDC/位流/Flash。

## 1. 冻结基线（只读，绝不修改）

| 项 | 路径 / SHA |
|----|-----------|
| 源软件基线 | `F:\FPGA_Work\sdr_full_chain_12class_combined_v1`（smoke_v1 位流 + smoke_v2 触摸软件） |
| 权威合并位流 | `combined_npu_hdmi_disable_icap.bit`（5,980,628 B，SHA `22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9`） |
| 十二类模型 | `model_12class/model_12class.raw`（SHA `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c`） |
| 类别契约 | `sdr_adapter/categories.hpp` `cat::target_12()`（12 类权威顺序） |

## 2. 拷贝清单（逐文件 SHA 见 SOURCE_PROVENANCE_SHA256.txt）

| 目录 | 拷贝文件数 | 状态 |
|------|-----------|------|
| board_package/ | 21 | verbatim（后续增量修改会标 `copied+modified`） |
| sdr_adapter/ | 35 | verbatim |
| ui_sw/ | 7 | verbatim |
| contracts/ | 3 | verbatim |
| model_12class/ | 4（json/raw/sha256/契约；不含 calibration/ 重编译数据） | verbatim |
| deployment_golden/ | 244 | verbatim |
| scripts/ | 13 | verbatim |
| host_tests/ | 14 | verbatim |
| docs/ | 16 | verbatim |
| **合计** | **359** | 全部 verbatim（2026-10-07 M0 拷贝，字节与源一致，模型 raw SHA 已复核） |

- 拷贝约定与 smoke_v2 冻结包一致：**排除** `.git`、日志、`*.o`、`bin/`、构建缓存、
  Vivado 工程副本、AutoDL 训练结果、重复位流、临时目录、`model_12class/calibration/cal_data`（重编译数据）。

## 3. 增量修改登记（本工程新增/改动，随里程碑更新）

| 文件 | 来源 | 改动类型 | 里程碑 | SHA256 |
|------|------|----------|--------|--------|
| `docs/TRAINING_SIGNAL_CONTRACT_AUDIT.md` | 新建 | 新增 | M0 | — |
| `docs/WAVEFORM_CONTRACT.md` | 新建 | 新增 | M0 | — |
| `SOURCE_PROVENANCE_SHA256.txt` | 新建 | 新增 | M0 | — |
| `sdr_adapter/signal_presence.hpp` | 新建 | 新增 | M1 | `44ac2e49…` |
| `host_tests/test_signal_presence.cpp` | 新建 | 新增 | M1 | `acaf7b2c…` |
| `docs/SIGNAL_PRESENCE_CONTRACT.md` | 新建 | 新增 | M1 | `58337290…` |
| `host_tests/build_host_tests.sh` | 拷贝 | copied+modified（追加 test_signal_presence/test_auto_level_control/test_dsp_measure/test_result_frame_v3/test_ui_v3_pages/test_mode_control/test_work_mode_engine/test_rf_waveform_12class/test_band_scan） | M1/M2/M3/M4/M5/M6/M7/M8/M9/M10 | `7a44f0e5…` |
| `host_tests/run_tests.sh` | 拷贝 | copied+modified（追加 test_signal_presence/test_auto_level_control/test_dsp_measure/test_result_frame_v3/test_ui_v3_pages/test_mode_control/test_work_mode_engine/test_rf_waveform_12class/test_band_scan） | M1/M2/M3/M4/M5/M6/M7/M8/M9/M10 | `08578f3e…` |
| `sdr_adapter/auto_level_control.hpp` | 新建 | 新增 | M2 | `1d3e942a…` |
| `host_tests/test_auto_level_control.cpp` | 新建 | 新增 | M2 | `66ce460c…` |
| `docs/AUTO_LEVEL_CONTROL_CONTRACT.md` | 新建 | 新增 | M2 | `6a3a6ba1…` |
| `docs/AUTO_LEVEL_MODEL_INPUT_AUDIT.md` | 新建 | 新增 | M2 | `00b5f34f…` |
| `sdr_adapter/dsp_measure.hpp` | 新建 | 新增 | M3 | `747fa1d0…` |
| `host_tests/test_dsp_measure.cpp` | 新建 | 新增 | M3 | `d9222713…` |
| `docs/DSP_MEASUREMENT_CONTRACT.md` | 新建 | 新增 | M3 | `f508c515…` |
| `sdr_adapter/result_frame.hpp` | 拷贝 | copied+modified（加 v3 扩展字段 has_measurements/measurements/presence_state/level_mode/model_scale/rf_gain_db） | M4 | `068d544b…` |
| `sdr_adapter/ui_report.hpp` | 拷贝 | copied+modified（新增 result_frame_v3_line，schema `12class-chain-v2`） | M4 | `a0cfcc9d…` |
| `board_package/result_frame_v2_parse.hpp` | 拷贝 | copied+modified（接受 v1+v2，解析 v3 扩展 + 嵌套 measurements） | M4 | `f082b68b…` |
| `host_tests/test_result_frame_v3.cpp` | 新建 | 新增 | M4 | `942b847d…` |
| `docs/RESULT_FRAME_PROTOCOL_AUDIT.md` | 新建 | 新增 | M4 | `3cb11dd4…` |
| `ui_sw/ui_render.hpp` | 拷贝 | copied+modified（MeasureView + UiState v3 字段 + render_parameters/render_mode 声明） | M5 | `4d77e030…` |
| `ui_sw/ui_render.cpp` | 拷贝 | copied+modified（新增 render_parameters/render_mode，导航标签改 CLASSIFY/PARAMETERS/MODE） | M5 | `3d8bfc15…` |
| `board_package/ui_state_map.hpp` | 拷贝 | copied+modified（map_to_state 填充 meas/presence/level_mode/model_scale/rf_gain_db） | M5 | `e2d1a881…` |
| `board_package/board_ui_live_12class.cpp` | 拷贝 | copied+modified（页面分发改 CLASSIFY/PARAMETERS/MODE） | M5 | `39f11b9f…` |
| `board_package/touch_geometry.hpp` | 拷贝 | copied+modified（注释：三区标签名更新，几何/状态机不变） | M5 | `0f968379…` |
| `host_tests/test_ui_v3_pages.cpp` | 新建 | 新增 | M5 | `f46f3b0c…` |
| `docs/THREE_PAGE_UI_CONTRACT.md` | 新建 | 新增 | M5 | `c3c207fb…` |
| `board_package/mode_control.hpp` | 新建 | 新增 | M6 | `f1c61537…` |
| `board_package/unix_socket_server.hpp` | 拷贝 | copied+modified（新增 reply() 非阻塞回写，仅控制通道用） | M6 | `eda39879…` |
| `board_package/board_ui_live_12class.cpp` | 拷贝 | copied+modified（接入 --ctl-sock 反向控制通道：排空/apply_command/reply/写 work_mode+running） | M6 | `d86b1cbc…` |
| `board_package/board_mode_ctl.cpp` | 新建 | 新增（一次性控制客户端） | M6 | `15577a26…` |
| `board_package/build_ui_live.sh` | 拷贝 | copied+modified（同时构建 board_mode_ctl，先构建后安装两者） | M6 | `5df32707…` |
| `ui_sw/ui_render.hpp` | 拷贝 | copied+modified（UiState 加 running） | M6 | `d8982c86…` |
| `ui_sw/ui_render.cpp` | 拷贝 | copied+modified（render_mode 加 run_state 行，移除 M6 占位行） | M6 | `34667c52…` |
| `scripts/mode_ctl.sh` | 新建 | 新增（board_mode_ctl 薄包装） | M6 | `5557090c…` |
| `scripts/stop_ui_live.sh` | 拷贝 | copied+modified（退出清理控制 socket） | M6 | `e740af9f…` |
| `host_tests/test_mode_control.cpp` | 新建 | 新增 | M6 | `e9378f29…` |
| `docs/MODE_CONTROL_CONTRACT.md` | 新建 | 新增 | M6 | `75236f30…` |
| `board_package/work_mode_engine.hpp` | 新建 | 新增（模式→幅度层映射+WorkModeDecision+ClassStabilityLock+WorkModeEngine） | M7/M8/M10（M10 加 reset_lock()） | `29997d03…` |
| `host_tests/test_work_mode_engine.cpp` | 新建 | 新增 | M7/M8 | `6e5bb137…` |
| `docs/WORK_MODE_ENGINE_CONTRACT.md` | 新建 | 新增 | M7/M8 | `c398a06e…` |
| `sdr_adapter/rf_waveform_12class.hpp` | 新建 | 新增（十二类确定性波形生成 + ×20 上采样） | M9 | `41e7be67…` |
| `host_tests/test_rf_waveform_12class.cpp` | 新建 | 新增（66 断言） | M9 | `24958cde…` |
| `board_package/board_gate10_selftest_12class.cpp` | 新建 | 新增（Gate 10 十二类 RF 自测） | M9 | `0c7a0f21…` |
| `docs/RF_SELF_TEST_CONTRACT.md` | 新建 | 新增 | M9 | `7eec75c1…` |
| `board_package/CMakeLists.txt` | 拷贝 | copied+modified（追加 Gate 10 目标 BUILD_GATE10） | M9 | `809921bb…` |
| `board_package/build_npu_on_board.sh` | 拷贝 | copied+modified（追加 --gate10 模式） | M9 | `0d3686ca…` |
| `scripts/run_gate10.sh` | 新建 | 新增（Gate 10 运行脚本） | M9 | `18bb7020…` |
| `host_tests/test_board_build.sh` | 拷贝 | copied+modified（追加 T21/T22/T23 覆盖 --gate10） | M9 | `71b00d76…` |
| `host_tests/syntax_check.sh` | 新建 | 新增（Gate 7/9/10 iCraft -fsyntax-only） | M9 | `5a2ff565…` |
| `board_package/band_scan.hpp` | 新建 | 新增（BAND SCAN LO 扫频时序 + 逐点聚合） | M10 | `47bfa6b8…` |
| `host_tests/test_band_scan.cpp` | 新建 | 新增（31 断言） | M10 | `cc2efcd5…` |
| `docs/BAND_SCAN_CONTRACT.md` | 新建 | 新增 | M10 | `5350ad66…` |
| `docs/OPEN_SOURCE_PARAMETER_MODEL_AUDIT.md` | 新建 | 新增（只读联网调研，无外部代码） | M11 | `491033c0…` |
| `docs/AUTONOMOUS_BOOT_FEASIBILITY_AUDIT.md` | 新建 | 新增（只读审计，不落地脚本/Flash） | M12 | `40922db7…` |
| `scripts/package_board_release_ui_v3.sh` | 新建 | 新增（UI-v3 板端包，确定性 tar GZIP=-n + --mtime + numeric-owner） | M13 | `6f4fa5a7…` |
| `board_package/producer_12class.hpp` | 新建 | 新增（Gate 9 实时生产者：DspMeasure+SignalPresence+WorkModeEngine+BandScanSequencer；model_scale 真实缩放输入、RF 增益真实写设备；反向控制通道唯一所有者） | M14 | `a44eeb8c…` |
| `board_package/board_gate9_full_chain_12class.cpp` | 拷贝 | copied+modified（run_loopback_phase → 连续生产者循环：--ctl-sock/--mode/--band-* + emit_frame_v3 + drain_control + PASS 门禁 presence/scan） | M14 | `a5830dc6…` |
| `board_package/board_ui_live_12class.cpp` | 拷贝 | copied+modified（移除反向控制通道，只显示生产者回传 work_mode/run_state，不自改） | M14 | `9a7b742a…` |
| `board_package/board_mode_ctl.cpp` | 拷贝 | copied+modified（注释：控制通道归 Gate 9 生产者） | M14 | `60683cd9…` |
| `board_package/board_gate10_selftest_12class.cpp` | 拷贝 | copied+modified（注释：独立自测，不产 v2、不喂 MODE/PARAMETERS） | M14 | `360733d0…` |
| `host_tests/test_producer_12class.cpp` | 新建 | 新增（生产者 5 组接线测试：参数非占位/无信号恢复/AUTO_LOCK/真实 LO 扫频/模式控制） | M14 | `6057aca4…` |
| `host_tests/test_result_frame_v3.cpp` | 拷贝 | copied+modified（work_mode/run_state 回环） | M14 | `046ee6ef…` |
| `host_tests/test_ui_v3_pages.cpp` | 拷贝 | copied+modified（生产者回传 work_mode/run_state 映射） | M14 | `d8b9af6a…` |
| `host_tests/build_host_tests.sh` | 拷贝 | copied+modified（追加 test_producer_12class） | M14 | `f1b01098…` |
| `host_tests/run_tests.sh` | 拷贝 | copied+modified（追加 test_producer_12class） | M14 | `592aba36…` |
| `scripts/stop_ui_live.sh` | 拷贝 | copied+modified（不再删控制 socket，控制通道归生产者） | M14 | `abfdcc25…` |
| `scripts/mode_ctl.sh` | 拷贝 | copied+modified（注释：控制通道归生产者） | M14 | `9a9da0cc…` |
| `docs/MODE_CONTROL_CONTRACT.md` | 拷贝 | copied+modified（生产者所有权 + test_producer_12class + 状态红线更新） | M14 | `24b3203b…` |
| `docs/BAND_SCAN_CONTRACT.md` | 拷贝 | copied+modified（§5 板端接线改为 M14 已真实执行） | M14 | `a87c2049…` |
| `docs/WORK_MODE_ENGINE_CONTRACT.md` | 拷贝 | copied+modified（§7 板端接线改为 M14 已真实执行） | M14 | `2330f939…` |
| `docs/SIGNAL_PRESENCE_CONTRACT.md` | 拷贝 | copied+modified（§6 标注 M14 已接线） | M14 | `2d8265ed…` |
| `docs/THREE_PAGE_UI_CONTRACT.md` | 拷贝 | copied+modified（§3/§4 UI 只显示生产者回传） | M14 | `b4281d9f…` |
| `docs/RF_SELF_TEST_CONTRACT.md` | 拷贝 | copied+modified（§8 Gate 10 独立自测 + 状态红线） | M14 | `332e5987…` |
| `docs/BOARD_LIVE_UI_TEST.md` | 拷贝 | copied+modified（标注历史 ui_v1 文档 + 状态红线） | M14 | `2685479c…` |
| `README.md` | 拷贝 | copied+modified（改为 ui_v3 生产者集成 README，不再冒充 combined_v1） | M14 | `7ed51aa0…` |
| `docs/AUTO_LEVEL_CONTROL_CONTRACT.md` | 拷贝 | copied+modified（状态行更新至生产者集成） | M14 | `e1cb65ca…` |
| `docs/DSP_MEASUREMENT_CONTRACT.md` | 拷贝 | copied+modified（状态行更新至生产者集成） | M14 | `80a49044…` |
| `docs/RESULT_FRAME_PROTOCOL_AUDIT.md` | 拷贝 | copied+modified（状态行/红线更新至生产者集成） | M14 | `3594d1c9…` |
| `docs/OPEN_SOURCE_PARAMETER_MODEL_AUDIT.md` | 拷贝 | copied+modified（红线更新至生产者集成） | M14 | `d1ff9c3a…` |

## 4. 状态红线

- 离线完成最高只标 **`READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST`**。
- 未经用户实机测试，不写 `UI_V3_HARDWARE_PASS / AUTO_LOCK_PASS / BAND_SCAN_PASS /
  12CLASS_RF_PASS / FINAL_MODEL_PASS / OOD_PASS / FULL_SYSTEM_FINAL_PASS`。
- 模型标签 `12CLASS_CHAIN_VALIDATION_MODEL`，OOD=NO_GO。
- 自主启动（M12）本轮只审计，最高标 `AUTONOMOUS_BOOT_FEASIBILITY_AUDITED`。
- 我禁碰板、禁写 Flash；上板由用户本人执行。

## 5. 交付物（M14 打包）

| 项 | 说明 |
|----|------|
| UI-v3 板端包 | `dist/sdr_full_chain_12class_ui_v3_board_package.tar.gz`（确定性 tar：`GZIP=-n` + `--mtime='UTC 2026-10-07'` + `--owner=0 --group=0 --numeric-owner`；内含 `SHA256SUMS.txt` 可 `sha256sum -c` 自校验）。tarball 自身 SHA256 见打包输出 / 交付纪要（不内嵌以免自引用）。 |
| 最终离线状态 | **`READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST`**（绝不写 *_PASS） |
