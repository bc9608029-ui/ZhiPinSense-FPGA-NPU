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
| `docs/MODE_CONTROL_CONTRACT.md` | 拷贝 | copied+modified（生产者所有权 + test_producer_12class + 状态红线更新；M15 状态红线刷新至 Gate10 显示控制完整性） | M14 | `e102dfa5…` |
| `docs/BAND_SCAN_CONTRACT.md` | 拷贝 | copied+modified（§5 板端接线改为 M14 已真实执行） | M14 | `a87c2049…` |
| `docs/WORK_MODE_ENGINE_CONTRACT.md` | 拷贝 | copied+modified（§7 板端接线改为 M14 已真实执行） | M14 | `2330f939…` |
| `docs/SIGNAL_PRESENCE_CONTRACT.md` | 拷贝 | copied+modified（§6 标注 M14 已接线） | M14 | `2d8265ed…` |
| `docs/THREE_PAGE_UI_CONTRACT.md` | 拷贝 | copied+modified（§3/§4 UI 只显示生产者回传） | M14 | `b4281d9f…` |
| `docs/RF_SELF_TEST_CONTRACT.md` | 拷贝 | copied+modified（§8 Gate 10 独立自测 + 状态红线；M15 状态红线刷新至 Gate10 显示控制完整性） | M14 | `ac34bc28…` |
| `docs/BOARD_LIVE_UI_TEST.md` | 拷贝 | copied+modified（标注历史 ui_v1 文档 + 状态红线） | M14 | `2685479c…` |
| `README.md` | 拷贝 | copied+modified（改为 ui_v3 生产者集成 README，不再冒充 combined_v1；M15 统一补丁章节 + 状态/目录刷新） | M14 | `815ea411…` |
| `docs/AUTO_LEVEL_CONTROL_CONTRACT.md` | 拷贝 | copied+modified（状态行更新至生产者集成） | M14 | `e1cb65ca…` |
| `docs/DSP_MEASUREMENT_CONTRACT.md` | 拷贝 | copied+modified（状态行更新至生产者集成） | M14 | `80a49044…` |
| `docs/RESULT_FRAME_PROTOCOL_AUDIT.md` | 拷贝 | copied+modified（状态行/红线更新至生产者集成） | M14 | `3594d1c9…` |
| `docs/OPEN_SOURCE_PARAMETER_MODEL_AUDIT.md` | 拷贝 | copied+modified（红线更新至生产者集成） | M14 | `d1ff9c3a…` |
| `board_package/board_gate10_selftest_12class.cpp` | 拷贝 | copied+modified（Task A 顺序自测：A3 逐类 stop+destroy→wait→create+push→recreate RX→丢弃 FIXED settle 帧、A4 hex seed、A5 12×20 终门禁；新增项1 `--dump-error-samples/--dump-dir` 误分类帧落盘） | M15 | `e7e04f13…` |
| `board_package/board_common.hpp` | 拷贝 | copied+modified（`opt_u64` 支持 `0x` 十六进制 + 拒绝前导符号） | M15 | `9b564257…` |
| `sdr_adapter/pluto_device.hpp` | 拷贝 | copied+modified（TX/RX 缓冲生命周期计数 `tx/rx_buffer_{create,destroy}_count` + `recreate_rx_buffer`，Mock 同步建模） | M15 | `788e151d…` |
| `sdr_adapter/pluto_device_libiio.cpp` | 拷贝 | copied+modified（缓冲生命周期计数 + `recreate_rx_buffer` 真实实现） | M15 | `9941907d…` |
| `sdr_adapter/crc32.hpp` | 新建 | 新增（TX 波形 crc32，`tx_waveform_crc32` 日志） | M15 | `26c5332f…` |
| `scripts/run_gate10.sh` | 拷贝 | copied+modified（顺序自测说明 + dump 用法注释） | M15 | `b5d3e8dd…` |
| `host_tests/test_gate10_sequential.cpp` | 新建 | 新增（Task A 顺序自测接线测试） | M15 | `2be6cd96…` |
| `docs/64QAM_PRECISION_DIAGNOSIS.md` | 新建 | 新增（新增项1：64QAM 17/20 归因流程 + 生成参数审计 + 交棒 V2，不重训） | M15 | `c1da4d24…` |
| `host_tools/compare_64qam_threeway.py` | 新建 | 新增（新增项1：ONNX fp32 / icraft-run --fake_qf / 板端 NPU 三方归因） | M15 | `dac17388…` |
| `board_package/board_ui_live_12class.cpp` | 拷贝 | copied+modified（Task B：`--display-diagnostic/--display-static/--display-refresh-hz` + 启动顺序 get2→清→sync→render→sync→设物理地址→submit→READY；运行时只画非扫描后缓冲） | M15 | `ba6beb46…` |
| `ui_sw/direct_framebuffer_backend.cpp` | 拷贝 | copied+modified（Task B：后缓冲翻转 + dirty-frame 诊断） | M15 | `14c0c8f0…` |
| `ui_sw/direct_framebuffer_backend.hpp` | 拷贝 | copied+modified（Task B） | M15 | `fcc24d2c…` |
| `scripts/run_display_integrity_test.sh` | 新建 | 新增（Task B：diagnostic/static/all 派发） | M15 | `f321e5ed…` |
| `host_tests/test_display_integrity.cpp` | 新建 | 新增（Task B 显示完整性） | M15 | `de7cf6a8…` |
| `board_package/control_channel.hpp` | 新建 | 新增（Task E：`CommandQueue/AckQueue/ControlState/ControlStats/control_thread_main`，控制线程只解析/入队） | M15 | `2c26957c…` |
| `board_package/mode_control.hpp` | 拷贝 | copied+modified（Task E：`apply_command/parse_command/ModeState/ModeKind/RunState`） | M15 | `bff99994…` |
| `board_package/board_gate9_full_chain_12class.cpp` | 拷贝 | copied+modified（Task E 控制线程 + 12 安全点唯一生产者 apply + ACCEPTED≤500ms/APPLIED≤2s + 新增项2 `--phase=ambient` rx-only 无信号集成） | M15 | `3debe094…` |
| `board_package/result_frame_v2_parse.hpp` | 拷贝 | copied+modified（Task E：`StateEvent` + `parse_state_event`） | M15 | `7ad62a19…` |
| `board_package/ui_state_map.hpp` | 拷贝 | copied+modified（Task E：`apply_state_event` 只改 mode/run 不碰分类） | M15 | `5380b247…` |
| `sdr_adapter/ui_report.hpp` | 拷贝 | copied+modified（Task E：`state_line` 控制状态事件行） | M15 | `1e3bd827…` |
| `scripts/test_mode_control_runtime.sh` | 新建 | 新增（Task E 板端实时控制响应自测） | M15 | `f86ff803…` |
| `host_tests/test_control_channel.cpp` | 新建 | 新增（Task E 控制通道） | M15 | `39b1599f…` |
| `board_package/gate9_phase.hpp` | 新建 | 新增（新增项2：`gate9::valid_phase` 含 ambient） | M15 | `1847ba7a…` |
| `scripts/run_no_signal_ambient.sh` | 新建 | 新增（新增项2 rx-only 无信号集成运行脚本） | M15 | `4f581829…` |
| `host_tests/test_no_signal_ambient.cpp` | 新建 | 新增（新增项2：无假分类不变式 + `--phase` CLI 表面） | M15 | `c21d2075…` |
| `host_tests/build_host_tests.sh` | 拷贝 | copied+modified（追加 test_control_channel/test_display_integrity/test_gate10_sequential/test_no_signal_ambient） | M15 | `aa6bbc01…` |
| `host_tests/run_tests.sh` | 拷贝 | copied+modified（同上） | M15 | `d077c07a…` |
| `docs/GATE10_DISPLAY_CONTROL_INTEGRITY_ACCEPTANCE.md` | 新建 | 新增（M15 统一补丁板端验收标准：Task A/B/E + 新增项1/2 硬门禁 + 红线） | M15 | `2c5739fa…` |
| `scripts/package_board_release_ui_v3.sh` | 拷贝 | copied+modified（追加 host_tools/ 打包） | M15 | `b48ed67f…` |
| `board_package/control_client.hpp` | 新建 | 新增（`ctl::ControlClient` 非阻塞 AF_UNIX 控制客户端；MSG_NOSIGNAL/丢写阻塞/粘行拼接/EOF 关闭；绝不 unlink 生产者 socket） | M16 | `f841deef…` |
| `board_package/touch_mode_control.hpp` | 新建 | 新增（`mctl::ControlTapDetector` + `mctl::ModeControlState`：两独立 pending 槽 mode_cmd_/run_cmd_、按下+释放=一tap、拖出取消、长按=一条命令、去抖、STOP 高优先级、旧 command_id 忽略、REJECTED/TIMEOUT 保留 applied、command_id=0 事件不解析） | M16 | `572bf5ef…` |
| `board_package/board_ui_live_12class.cpp` | 拷贝 | copied+modified（M16 控制客户端 `--ctl-sock/--control-timeout-ms/--control-reconnect-ms` + 第三页触摸按钮接线 + 状态机 sync/observe applied + 断开清 pending/重连发 STATUS + UI_CTL/TOUCH_CONTROL 统计与结果行） | M16 | `3d487549…` |
| `ui_sw/ui_render.hpp` | 拷贝 | copied+modified（UiState M16 字段 requested_mode/requested_running/ctl_connected/last_command/command_status/control_taps + `ui::mode_ui` 几何单源 button_rect） | M16 | `b7be6206…` |
| `ui_sw/ui_render.cpp` | 拷贝 | copied+modified（render_mode 第三页三模式按钮 + START/STOP + 六行详情卡；高亮=applied；command_status 配色） | M16 | `dd738627…` |
| `host_tests/build_host_tests.sh` | 拷贝 | copied+modified（追加 test_touch_mode_control） | M16 | `f932f40f…` |
| `host_tests/run_tests.sh` | 拷贝 | copied+modified（同上） | M16 | `cf667aa5…` |
| `host_tests/test_touch_mode_control.cpp` | 新建 | 新增（86 断言：tap/拖出/长按/去抖/五按钮映射/幂等/duplicate/STOP 高优先级/两槽并发/ACCEPTED 记 id/APPLIED 按 id/旧 id 忽略/REJECTED/TIMEOUT 保留/state by-id+by-target/command_id=0 不解析/frame 仅推进/STATUS/断开清 pending/经真实控制线程+ControlClient 全链路回环） | M16 | `3ba64806…` |
| `scripts/test_touch_mode_control.sh` | 新建 | 新增（M16 板端验收：prep/supervision/logging，**不使用 mode_ctl.sh 替代手工触摸**；抓 TOUCH_CONTROL_RESULT） | M16 | `d5454605…` |
| `docs/TOUCH_MODE_CONTROL_CONTRACT.md` | 新建 | 新增（M16 触摸模式控制契约：架构硬约束/几何/协议/状态机不变式/触摸规则/CLI/主机测试/板端验收/红线） | M16 | `ec4d1d1d…` |
| `README.md` | 拷贝 | copied+modified（M16 触摸模式控制章节 + 状态/里程碑/目录刷新） | M16 | `993c64f6…` |
| `board_package/gate10_settle.hpp` | 新建 | 新增（Task A/B/C 纯逻辑：SettlePolicy/TIME_ONLY/parse_settle_config fail-closed + LifecycleDeltas + ErrorClassFilter） | M17 | `474e1aa8…` |
| `board_package/ui_dirty_state.hpp` | 新建 | 新增（Task E/G：display_changed + FlipScheduler 事件驱动翻转） | M17 | `97e55568…` |
| `board_package/board_gate10_selftest_12class.cpp` | 拷贝 | copied+modified（Task A 删 settle 捕获-丢弃路径 + Task B 生命周期快照移到析构/recreate 之后 + Task C dump 富化） | M17 | `53edbfd0…` |
| `board_package/board_ui_live_12class.cpp` | 拷贝 | copied+modified（Task E/G 事件驱动翻转 + Task F 启动消隐；M16 触摸/控制客户端全保留） | M17 | `cb7f6493…` |
| `ui_sw/direct_framebuffer_backend.cpp` | 拷贝 | copied+modified（Task F set_display_enable 写 disable_hdmi） | M17 | `a0a05142…` |
| `ui_sw/direct_framebuffer_backend.hpp` | 拷贝 | copied+modified（Task F set_display_enable 声明 + 启动条纹注释） | M17 | `ff6a382c…` |
| `sdr_adapter/sha256.hpp` | 新建 | 新增（Task C：header-only FIPS 180-4 SHA256 + sha256_hex_file + self_test） | M17 | `c7603b4c…` |
| `scripts/common.sh` | 拷贝 | copied+modified（新增 BITSTREAM_SHA 供 Gate 10 dump 富化） | M17 | `f10e55f9…` |
| `scripts/run_gate10.sh` | 拷贝 | copied+modified（默认 --settle-frames=0 + --settle-wait-ms=100 + --bitstream-sha） | M17 | `84d7a7f4…` |
| `host_tests/test_gate10_settle.cpp` | 新建 | 新增（27 断言：settle 配置/lifecycle/dump-filter） | M17 | `e30dc80c…` |
| `host_tests/test_ui_scheduler.cpp` | 新建 | 新增（22 断言：display_changed/FlipScheduler） | M17 | `d7006c4b…` |
| `host_tests/test_display_integrity.cpp` | 拷贝 | copied+modified（新增 test_display_enable 15 断言，总 59） | M17 | `cc37798f…` |
| `host_tests/build_host_tests.sh` | 拷贝 | copied+modified（追加 test_ui_scheduler/test_gate10_settle） | M17 | `0a0f02e2…` |
| `host_tests/run_tests.sh` | 拷贝 | copied+modified（同上） | M17 | `10577310…` |
| `docs/FRAMEBUFFER_VBLANK_AUDIT.md` | 新建 | 新增（Task D 只读审计：翻转无 vblank 同步、启动条纹复位地址残留） | M17 | `0b026f47…` |
| `docs/M17_HARDWARE_FINDINGS.md` | 新建 | 新增（§2 板端实测发现转录 + 根因→修复映射） | M17 | `71d19251…` |
| `docs/M17_BOARD_ACCEPTANCE.md` | 新建 | 新增（M17 板端验收硬门禁 A1–H1） | M17 | `0c4d3255…` |
| `README.md` | 拷贝 | copied+modified（M17 章节 + 状态/里程碑/目录刷新） | M17 | `38203537…` |
| `docs/M17_BOARD_ACCEPTANCE.md` | 拷贝 | copied+modified（M17.1：启动条纹 F1 拆 F1a/F1b + 触摸验收 H1 顺序修正 + 结论红线刷新） | M17.1 | `3a3e181c…` |
| `docs/FRAMEBUFFER_VBLANK_AUDIT.md` | 拷贝 | copied+modified（M17.1：§6 Task F 澄清为 F1b 范围 + 新增 §7 NEEDS-RTL-BLANK-ON-RESET 未来 RTL 任务） | M17.1 | `024e1219…` |
| `docs/TOUCH_MODE_CONTROL_CONTRACT.md` | 拷贝 | copied+modified（M17.1：§8 板端验收顺序修正为 UI-first + 长运行 digital 生产者 + run_m17_touch_acceptance.sh） | M17.1 | `c377285a…` |
| `scripts/test_touch_mode_control.sh` | 拷贝 | copied+modified（M17.1：头注释 offline→digital 长运行生产者 + 新增 --control-sock 参数） | M17.1 | `ca5dc3b7…` |
| `scripts/run_m17_touch_acceptance.sh` | 新建 | 新增（M17.1：一键触摸验收编排，14 行为 UI-first/digital 生产者/控制 socket/rec_scale fail-closed/--rec-scale 覆盖/结果判定委托） | M17.1 | `bf82fdab…` |
| `scripts/test_m17_touch_acceptance.sh` | 新建 | 新增（M17.1：编排脚本 14 行为主机侧 shell 一致性测试，36 断言） | M17.1 | `bcd9441a…` |
| `README.md` | 拷贝 | copied+modified（M17.1：Task F/H 勘误 + M17.1 章节 + 状态红线刷新） | M17.1 | `8145800e…` |
| `scripts/process_guard.sh` | 新建 | 新增（纯 /proc 进程/日志/socket 安全助手：pid_alive/pid_exe/pid_matches_bin/find_pids_named/socket_served/socket_inode/socket_served_by/stop_pid/log_offset_of/tail_since/run_id_new；无 lsof/fuser/pgrep 依赖） | M17.2 | `02fac1f0…` |
| `scripts/run_m17_touch_acceptance.sh` | 拷贝 | copied+modified（M17.2 十项硬化：有限 producer frames=2000000、stop_stale_services+confirm_services_stopped、pid_matches_bin/socket_served_by 校验、run_id+日志偏移门控、--ctl-sock 双端传递、control socket 缺失 fail-closed、严格单行 rec_scale、EXIT/INT/TERM 只终止本轮 PID） | M17.2 | `3a335385…` |
| `scripts/test_touch_mode_control.sh` | 拷贝 | copied+modified（M17.2：--ui-log/--log-offset/--run-id 参数 + socket_served fail-closed + await_result 只认偏移后结果 + tail -n 0 -F 只显示本轮） | M17.2 | `43fe59c8…` |
| `scripts/test_m17_touch_acceptance.sh` | 拷贝 | copied+modified（M17.2：编排脚本主机侧 shell 一致性测试，65 断言，含旧日志假 PASS/旧 socket/孤儿清理/自定义 socket 四场景单元测试） | M17.2 | `c25afdc9…` |
| `docs/M17_BOARD_ACCEPTANCE.md` | 拷贝 | copied+modified（M17.2：§4 新增 H2 编排脚本加固 + §5 结论红线刷新） | M17.2 | `421a5392…` |
| `docs/TOUCH_MODE_CONTROL_CONTRACT.md` | 拷贝 | copied+modified（M17.2：§8.1 编排脚本加固 + §9 状态红线刷新） | M17.2 | `5de1b19e…` |
| `README.md` | 拷贝 | copied+modified（M17.2：脚本加固章节 + 里程碑 + 主机验证 65 断言 + 状态红线刷新） | M17.2 | `85dfe239…` |
| `scripts/process_guard.sh` | 拷贝 | copied+modified（M17.3：新增 `stop_pid_if_matches <pid> <bin>`——kill 前先确认 PID 仍存活且可执行文件精确等于 bin，已退出/被复用一律不信号） | M17.3 | `2be1aed4…` |
| `scripts/run_m17_touch_acceptance.sh` | 拷贝 | copied+modified（M17.3 四项修正：LOG_OFFSET 移到 UI 启动+socket 归属+PID 验证成功后采集；默认 producer frames=50000；_cleanup 改用 stop_pid_if_matches 重验 PID 身份；UI PID 文件缺失/空/非纯数字/身份不符 fail-closed） | M17.3 | `abac268b…` |
| `scripts/test_m17_touch_acceptance.sh` | 拷贝 | copied+modified（M17.3：§1 frames 50000 + §8 stop_pid_if_matches + 新增 §15–§18：LOG_OFFSET 顺序 / PID 文件 fail-closed / 旧日志大于新日志回归 / stop_pid_if_matches 功能，78 断言） | M17.3 | `b1363052…` |
| `docs/M17_BOARD_ACCEPTANCE.md` | 拷贝 | copied+modified（M17.3：§4 新增 H3 最小脚本补丁 + §5 结论红线刷新） | M17.3 | `32072fae…` |
| `docs/TOUCH_MODE_CONTROL_CONTRACT.md` | 拷贝 | copied+modified（M17.3：§8.2 最小脚本补丁 + §9 状态红线刷新） | M17.3 | `3c695c9b…` |
| `README.md` | 拷贝 | copied+modified（M17.3：最小脚本补丁章节 + 里程碑 + 主机验证 78 断言 + 状态红线刷新） | M17.3 | `346b7ec2…` |

## 4. 状态红线

- 离线完成最高只标 **`READY-FOR-M17.3-TOUCH-ACCEPTANCE`**
  （M17.3 触摸验收编排最小脚本补丁；M17.2 的
  `READY-FOR-M17.2-HARDENED-TOUCH-ACCEPTANCE`、M17.1 的
  `READY-FOR-M17.1-CORRECTED-HARDWARE-ACCEPTANCE` 及更早的
  `READY-FOR-M17-GATE10-UI-INTEGRITY-AND-TOUCH-HARDWARE-TEST` /
  `READY-FOR-TOUCH-MODE-CONTROL-HARDWARE-TEST` /
  `READY-FOR-GATE10-DISPLAY-AND-CONTROL-INTEGRITY-HARDWARE-TEST` /
  `READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST` 已被本增量吸收）。
- 启动条纹 F1a（位流加载 → UI 启动前）只记录、标 **`NEEDS-RTL-BLANK-ON-RESET`**（未来 RTL
  任务，见 `docs/FRAMEBUFFER_VBLANK_AUDIT.md` §7）；软件不宣称根治，F1b 才是 M17 软件保证范围。
- 未经用户实机测试，不写 `UI_V3_HARDWARE_PASS / AUTO_LOCK_PASS / BAND_SCAN_PASS /
  12CLASS_RF_PASS / FINAL_MODEL_PASS / OOD_PASS / FULL_SYSTEM_FINAL_PASS /
  GATE10_DISPLAY_CONTROL_INTEGRITY_PASS / 64QAM_PASS / TOUCH_MODE_CONTROL_HARDWARE_PASS /
  GATE10_PASS / SCREEN_PASS / FULL_CHAIN_HARDWARE_PASS / PROJECT_COMPLETE`。
- 模型标签 `12CLASS_CHAIN_VALIDATION_MODEL`，OOD=NO_GO。
- 自主启动（M12）本轮只审计，最高标 `AUTONOMOUS_BOOT_FEASIBILITY_AUDITED`。
- 64QAM（M15 17/20、M17 A/B 对照 16/20）仅诊断归因 int8 量化精度，**不重训/不换模型/
  不调门限/不挑种子**；交棒 `ad_amr_12class_robust_v2`。
- 我禁碰板、禁写 Flash；上板由用户本人执行。

## 5. 交付物（M15 打包）

| 项 | 说明 |
|----|------|
| M14 全量包（历史，**不改动**） | `dist/sdr_full_chain_12class_ui_v3_board_package.tar.gz` — SHA256 `e6d7f8d6cb5dd8a693c177971675cb34caa6224c55142ac179bc4f53d1448462`，399 文件，M14 生产者集成内容（**不含** M15/host_tools/）。 |
| M15 统一补丁（增量） | `dist/gate10_display_control_integrity_fix_patch.tar.gz` — SHA256 `0d871469fd3849be8a6dd52019bf73769d6f3b54193838cd85ecdc38b7cd19ce`，108,191 B，34 文件（M15 相对 M14 的全部新增/改动文件；解包后覆盖到已解包的 M14 板端包根目录即可）。 |
| M15 全量包（版本化新增） | `dist/sdr_full_chain_12class_ui_v3_board_package_m15.tar.gz` — SHA256 `d74158d03721988cd894a83af105dc44bfebeb8bfe0b438e89f7fcc328cbaeaf`，2,973,019 B，412 文件；内容 ≡「M14 全量包解包 + 叠加 M15 补丁」，已含 host_tools/；确定性 tar（`GZIP=-n` + `--mtime='UTC 2026-10-07'` + `--owner=0 --group=0 --numeric-owner`），独立解包 `sha256sum -c SHA256SUMS.txt` 全 OK。 |
| 最终离线状态 | **`READY-FOR-GATE10-DISPLAY-AND-CONTROL-INTEGRITY-HARDWARE-TEST`**（绝不写 *_PASS） |

## 6. 交付物（M16 打包）

| 项 | 说明 |
|----|------|
| M15 全量包（历史，**不改动**） | `dist/sdr_full_chain_12class_ui_v3_board_package_m15.tar.gz` — SHA256 `d74158d03721988cd894a83af105dc44bfebeb8bfe0b438e89f7fcc328cbaeaf`，2,973,019 B，412 文件（M15 统一补丁内容）。 |
| M16 触摸模式控制补丁（增量） | `dist/touch_mode_control_m16_patch.tar.gz` — 12 文件（M16 相对 M15 的全部新增/改动文件：10 代码/文档 + PROVENANCE.md + README.md + SHA256SUMS.txt）；解包后覆盖到已解包的 M15 板端包根目录即可。 |
| M16 全量包（版本化新增） | `dist/sdr_full_chain_12class_ui_v3_board_package_m16.tar.gz` — SHA256 `47b599dc01e557835853c42265977c54071cb0138482c832cab6c3da0fa44590`，2,990,484 B；内容 ≡「M15 全量包解包 + 叠加 M16 补丁」；确定性 tar（`GZIP=-n` + `--mtime='UTC 2026-10-07'` + `--owner=0 --group=0 --numeric-owner`），独立解包 `sha256sum -c SHA256SUMS.txt` 全 OK。 |
| 最终离线状态 | **`READY-FOR-TOUCH-MODE-CONTROL-HARDWARE-TEST`**（绝不写 *_PASS） |

## 7. 交付物（M17 打包）

| 项 | 说明 |
|----|------|
| M16 全量包（历史，**不改动**） | `dist/sdr_full_chain_12class_ui_v3_board_package_m16.tar.gz` — SHA256 `47b599dc01e557835853c42265977c54071cb0138482c832cab6c3da0fa44590`，2,990,484 B（M17 的强制基线，已核验）。 |
| M17 集成补丁（增量） | `dist/gate10_ui_integrity_m17_patch.tar.gz` — M17 相对 M16 的全部新增/改动文件（17 代码/文档 + README.md + PROVENANCE.md + SHA256SUMS.txt，共 20 文件）；解包后覆盖到已解包的 M16 板端包根目录即可。 |
| M17 全量包（版本化新增） | `dist/sdr_full_chain_12class_ui_v3_board_package_m17.tar.gz` — 内容 ≡「M16 全量包解包 + 叠加 M17 补丁」；确定性 tar（`GZIP=-n` + `--mtime='UTC 2026-10-07'` + `--owner=0 --group=0 --numeric-owner`），独立解包 `sha256sum -c SHA256SUMS.txt` 全 OK。 |
| 最终离线状态 | **`READY-FOR-M17-GATE10-UI-INTEGRITY-AND-TOUCH-HARDWARE-TEST`**（绝不写 *_PASS） |

## 8. 交付物（M17.1 打包）

| 项 | 说明 |
|----|------|
| M17 全量包（历史，**不改动**） | `dist/sdr_full_chain_12class_ui_v3_board_package_m17.tar.gz` — SHA256 `55ceabb73cc4b0d891ecf6206d49db33604aa7fc53e4ce34d1211a60ca0d2404`（M17.1 的强制基线，见 §7）。 |
| M17.1 验收勘误补丁（增量） | `dist/m17_1_acceptance_errata_patch.tar.gz` — M17.1 相对 M17 的全部新增/改动文件（6 代码/文档 + README.md + PROVENANCE.md + SHA256SUMS.txt，共 9 文件）；解包后覆盖到已解包的 M17 板端包根目录即可。 |
| M17.1 全量包（版本化新增） | `dist/sdr_full_chain_12class_ui_v3_board_package_m17_1.tar.gz` — 内容 ≡「M17 全量包解包 + 叠加 M17.1 补丁」；确定性 tar（`GZIP=-n` + `--mtime='UTC 2026-10-07'` + `--owner=0 --group=0 --numeric-owner`），独立解包 `sha256sum -c SHA256SUMS.txt` 全 OK。 |
| 最终离线状态 | **`READY-FOR-M17.1-CORRECTED-HARDWARE-ACCEPTANCE`**（绝不写 *_PASS） |

## 9. 交付物（M17.2 打包）

| 项 | 说明 |
|----|------|
| M17.1 全量包（历史，**不改动**） | `dist/sdr_full_chain_12class_ui_v3_board_package_m17_1.tar.gz` — SHA256 `78dabf8158ce3bea05744d0c40d220e6c91ee6d1ad839ba611dc6744850e40a6`（M17.2 的强制基线，见 §8）。 |
| M17.2 脚本加固补丁（增量） | `dist/m17_2_touch_acceptance_harden_patch.tar.gz` — M17.2 相对 M17.1 的全部新增/改动文件（7 代码/文档 + PROVENANCE.md + SHA256SUMS.txt，共 9 文件）；解包后覆盖到已解包的 M17.1 板端包根目录即可。 |
| M17.2 全量包（版本化新增） | `dist/sdr_full_chain_12class_ui_v3_board_package_m17_2.tar.gz` — 内容 ≡「M17.1 全量包解包 + 叠加 M17.2 补丁」；确定性 tar（`GZIP=-n` + `--mtime='UTC 2026-10-07'` + `--owner=0 --group=0 --numeric-owner`），独立解包 `sha256sum -c SHA256SUMS.txt` 全 OK。 |
| 最终离线状态 | **`READY-FOR-M17.2-HARDENED-TOUCH-ACCEPTANCE`**（绝不写 *_PASS） |

## 10. 交付物（M17.3 打包）

| 项 | 说明 |
|----|------|
| M17.2 全量包（历史，**不改动**） | `dist/sdr_full_chain_12class_ui_v3_board_package_m17_2.tar.gz` — SHA256 `66817b65…`（M17.3 的强制基线，见 §9）。 |
| M17.3 最小脚本补丁（增量） | `dist/m17_3_minimal_script_patch.tar.gz` — M17.3 相对 M17.2 的全部新增/改动文件（6 代码/文档 + PROVENANCE.md + SHA256SUMS.txt，共 8 文件）；解包后覆盖到已解包的 M17.2 板端包根目录即可。 |
| M17.3 全量包（版本化新增） | `dist/sdr_full_chain_12class_ui_v3_board_package_m17_3.tar.gz` — 内容 ≡「M17.2 全量包解包 + 叠加 M17.3 补丁」；确定性 tar（`GZIP=-n` + `--mtime='UTC 2026-10-07'` + `--owner=0 --group=0 --numeric-owner`），独立解包 `sha256sum -c SHA256SUMS.txt` 全 OK。 |
| 最终离线状态 | **`READY-FOR-M17.3-TOUCH-ACCEPTANCE`**（绝不写 *_PASS） |
