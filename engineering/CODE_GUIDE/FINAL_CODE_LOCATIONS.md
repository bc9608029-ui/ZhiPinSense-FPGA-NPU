# 最终代码从哪里开始看

本页依据正式快照内的systemd服务、deployment_launcher.py和run_candidate_finalize_v2.py实际命令追踪，区别“实际调用链”与“历史源码来源”。导航不修改运行功能，也不重新证明某次硬件测试。

## 最终板端主链

以下路径相对于工程根目录，点击[模块与关键入口](MODULE_ENTRY_POINTS.md)可直接进入对应文件。

1. `FINAL_BOARD_SNAPSHOT_20261102/release/rml24-integrated.service` 启动 `deployment_launcher.py`。
2. 启动器校验晋级回执及文件身份，然后执行 `scripts/run_candidate_finalize_v2.py`。某些源码首部还保留早期candidate注释，不能据旧注释判定快照未部署。
3. 监管器实际启动 `candidate/rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py`；该包装器调用 `standalone_receiver.py`，接入 `repeat_mean_candidate.py` 与 `gain_freeze_radio.py`。恢复核心与two-DC在同一快照的 `runtime/receiver_core.py` 和 `recovery/candidate_two_dc.py`。
4. 频率与模式逻辑继续阅读 `runtime/standalone_control.py`、`continuous_sweep.py`、`scan_lock_policy.py`、`radio_tuning.py` 及 `board_runtime/rml24_dualmode_receiver_centered_v2.py`，并结合实际import关系判断启用路径。
5. UI可执行程序是 `candidate/bin/board_ui_live_rml24_final`；源码入口为 `candidate/board_package/board_ui_live_rml24_final.cpp`，绘制实现位于 `candidate/ui_sw/ui_render.cpp`，历史记录位于 `candidate/ui_sw/signal_history.hpp`，触摸及频率输入见board_package中对应头文件。

## NPU、模型与外部程序

监管器实际通过hardware_restart_guard启动板上 `/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared`，并核对该二进制SHA；不是只凭目录名选一个npu_stream.cpp。其源码在历史去重树中，请在关键入口表点击 `shared_owner/npu_stream_shared.cpp`。外部程序不在release目录内并不等于缺失，具体身份见 `FINAL_BOARD_SNAPSHOT_20261102/EXTERNAL_IDENTITY_VERIFICATION.json`。

网络结构优先看 `TRAINING_REFERENCE/rml24_net.py`，所选检查点为 `rml24_seed2027_best.pt`，参数和部署对应关系见 `TRAINING_VERIFIED.json`。板端部署模型为 `rml24_adamrv11_bf16.json/.raw`，身份在正式监管器及外部核验记录中；在逐文件索引按该名称搜索即可找到归档中的实际文件。完整训练工程原路径以 `sdr_amr_rml24_ood_v1_1` 检索 `ORIGINAL_PATH_INDEX.csv`，不将早期8类/23类模型当成最终24类模型。

## FPGA频谱侧路

监管器传入 `--spectrum-backend fpga` 与外部 `scan_xrt` 驱动路径。RTL和构建脚本的原始工程位置为 `FPGA_Work/smartscan_prefetch_fix3_20261031/fpga/`，通过原路径索引定位实际去重文件；关键入口表提供smart_scan_top.sv、scan_xrt.cpp和布局布线脚本的可点击链接。顶层复用、IP、XDC与相应Tcl要结合完整工程阅读，不是单个RTL文件就能重建整机。FPGA用于显示频谱，不将它描述为最终NPU分类主链中的全部特征计算。

## PC独立发射端

`MULTIFREQUENCY_TX_CANDIDATE_20261102/START_TX_CONSOLE.cmd` → `pc_console/app.py`。单路控制看 `tx_core.py/tx_worker.py`；多路设置与工作进程看 `multi_dialog.py/multi_core.py/multi_worker.py`；依赖和状态看该目录交接。最新移动盘启动补充在 `LATEST_PC_LAUNCHER_20261102`。PC不把真实类别传给接收分类服务。

## 查任意其他文件

在[离线搜索页](FILE_BROWSER.html)或 `FILE_INDEX.csv` 中查实际文件路径、模块与符号；查恢复前原始路径用 `ORIGINAL_PATH_INDEX.csv`。正式快照也收录兼容源码，历史目录更不代表所有文件同时启用；最终定位需要沿启动与import/include调用链阅读。厂商依赖和生成网表遵守原许可。

详细AI辅助范围见[llm_usage.md](llm_usage.md)。原12244项文件的原始校验清单保留在工程根目录 `SHA256SUMS_ORIGINAL.txt`，新增材料由 `SHA256SUMS.txt` 校验。
