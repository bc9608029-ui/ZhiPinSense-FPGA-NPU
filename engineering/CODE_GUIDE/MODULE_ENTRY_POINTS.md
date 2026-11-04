# 模块与关键入口

以下路径均指向归档中实际存在的文件；目录名、旧注释或candidate字样本身不是部署状态证明，正式状态以快照回执与启动路径为准。

| 所属模块 | 文件 | 阅读用途 |
|---|---|---|
| 启动部署与运行管理 | [FINAL_BOARD_SNAPSHOT_20261102/release/rml24-integrated.service](../FINAL_BOARD_SNAPSHOT_20261102/release/rml24-integrated.service) | systemd服务入口；启动deployment_launcher.py |
| 启动部署与运行管理 | [FINAL_BOARD_SNAPSHOT_20261102/release/deployment_launcher.py](../FINAL_BOARD_SNAPSHOT_20261102/release/deployment_launcher.py) | 正式快照启动器；核对晋级回执和文件身份，等待USB/显示节点，再启动前台监管器 |
| 启动部署与运行管理 | [FINAL_BOARD_SNAPSHOT_20261102/release/scripts/run_candidate_finalize_v2.py](../FINAL_BOARD_SNAPSHOT_20261102/release/scripts/run_candidate_finalize_v2.py) | 进程监管与预检；管理接收、NPU和UI子进程生命周期 |
| 启动部署与运行管理 | [FINAL_BOARD_SNAPSHOT_20261102/release/boot_recovery.py](../FINAL_BOARD_SNAPSHOT_20261102/release/boot_recovery.py) | 启动时硬件准备及恢复辅助；结合启动器调用阅读 |
| 接收恢复与频率模式 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/runtime/receiver_core.py](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/runtime/receiver_core.py) | 接收核心及其辅助函数；与模式控制、恢复模块结合阅读 |
| 接收恢复与频率模式 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/runtime/continuous_sweep.py](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/runtime/continuous_sweep.py) | 连续巡扫逻辑；结合接收入口与控制接口阅读 |
| 历史工程与辅助文件 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/runtime/standalone_control.py](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/runtime/standalone_control.py) | 独立接收控制与界面状态更新接口 |
| 接收恢复与频率模式 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/runtime/scan_lock_policy.py](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/runtime/scan_lock_policy.py) | 搜索与保持锁定策略 |
| 接收恢复与频率模式 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/runtime/radio_tuning.py](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/runtime/radio_tuning.py) | 射频调谐辅助与频率处理 |
| 历史工程与辅助文件 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/runtime/spectrum_backend.py](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/runtime/spectrum_backend.py) | 频谱后端接口；显示侧路与模型输入分开理解 |
| 接收恢复与频率模式 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py) | 监管器实际启动的接收入口；校验冻结依赖、接入重复载荷平均和增益处理 |
| 接收恢复与频率模式 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/board_runtime/standalone_receiver.py](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/board_runtime/standalone_receiver.py) | 接收服务主流程；由repeat-mean包装入口调用 |
| 接收恢复与频率模式 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/board_runtime/repeat_mean_candidate.py](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/board_runtime/repeat_mean_candidate.py) | 八段重复载荷的预处理实现；与接收包装入口配合 |
| 接收恢复与频率模式 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/board_runtime/gain_freeze_radio.py](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/board_runtime/gain_freeze_radio.py) | 自动选择接收增益后冻结的接入包装 |
| 接收恢复与频率模式 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/board_runtime/bounded_input_gain.py](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/board_runtime/bounded_input_gain.py) | 模型输入的有限幅度处理；不是全局自由归一化 |
| 接收恢复与频率模式 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/recovery/candidate_two_dc.py](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/rml24_final/recovery/candidate_two_dc.py) | 正式快照内的two-DC恢复实现；优先于历史来源阅读 |
| 接收UI与触摸交互 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/board_package/board_ui_live_rml24_final.cpp](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/board_package/board_ui_live_rml24_final.cpp) | 最终UI可执行程序的C++入口 |
| 接收UI与触摸交互 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/ui_sw/ui_render.cpp](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/ui_sw/ui_render.cpp) | 最终UI绘制实现；通过ui_render.hpp被UI入口调用 |
| 接收UI与触摸交互 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/ui_sw/signal_history.hpp](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/ui_sw/signal_history.hpp) | 最终UI入口包含的历史记录管理与显示相关接口 |
| 接收UI与触摸交互 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/board_package/frequency_control.hpp](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/board_package/frequency_control.hpp) | 触摸频率输入及控制交互 |
| 接收UI与触摸交互 | [FINAL_BOARD_SNAPSHOT_20261102/release/candidate/board_package/touch_evdev.hpp](../FINAL_BOARD_SNAPSHOT_20261102/release/candidate/board_package/touch_evdev.hpp) | Linux输入事件触摸读取 |
| 模型训练与NPU推理 | [TRAINING_REFERENCE/rml24_net.py](../TRAINING_REFERENCE/rml24_net.py) | 24类网络源码；优先核对ADAMRV11Net与检查点身份 |
| 模型训练与NPU推理 | [TRAINING_REFERENCE/rml24_seed2027_best.pt](../TRAINING_REFERENCE/rml24_seed2027_best.pt) | 最终所选训练检查点；不是板端直接运行程序 |
| 模型训练与NPU推理 | [TRAINING_REFERENCE/TRAINING_VERIFIED.json](../TRAINING_REFERENCE/TRAINING_VERIFIED.json) | 模型参数、训练选择和部署对应关系的核验记录 |
| 模型训练与NPU推理 | [TRAINING_REFERENCE/rml24_base.yaml](../TRAINING_REFERENCE/rml24_base.yaml) | 基础训练配置；所选试验参数须结合核验记录 |
| PC发射与公共帧 | [MULTIFREQUENCY_TX_CANDIDATE_20261102/START_TX_CONSOLE.cmd](../MULTIFREQUENCY_TX_CANDIDATE_20261102/START_TX_CONSOLE.cmd) | PC发射控制启动脚本 |
| PC发射与公共帧 | [MULTIFREQUENCY_TX_CANDIDATE_20261102/pc_console/app.py](../MULTIFREQUENCY_TX_CANDIDATE_20261102/pc_console/app.py) | PC控制台主界面与操作入口 |
| PC发射与公共帧 | [MULTIFREQUENCY_TX_CANDIDATE_20261102/pc_console/multi_dialog.py](../MULTIFREQUENCY_TX_CANDIDATE_20261102/pc_console/multi_dialog.py) | 多频点参数设置界面 |
| PC发射与公共帧 | [MULTIFREQUENCY_TX_CANDIDATE_20261102/pc_console/multi_core.py](../MULTIFREQUENCY_TX_CANDIDATE_20261102/pc_console/multi_core.py) | 多频点合成核心及相关合同 |
| PC发射与公共帧 | [MULTIFREQUENCY_TX_CANDIDATE_20261102/pc_console/multi_worker.py](../MULTIFREQUENCY_TX_CANDIDATE_20261102/pc_console/multi_worker.py) | 多频点硬件发射工作进程 |
| PC发射与公共帧 | [MULTIFREQUENCY_TX_CANDIDATE_20261102/pc_console/tx_worker.py](../MULTIFREQUENCY_TX_CANDIDATE_20261102/pc_console/tx_worker.py) | 单信号硬件发射工作进程 |
| FPGA与PS/PL接口 | [source/嵌赛/rml24_fpga_smartscan_prep2_20261028/rtl/smart_scan_top.sv](../source/%E5%B5%8C%E8%B5%9B/rml24_fpga_smartscan_prep2_20261028/rtl/smart_scan_top.sv) | FPGA频谱处理RTL顶层（原始最新工程路径由去重映射定位） |
| 接收恢复与频率模式 | [source/嵌赛/amr_rescue_gmsk_candidate_20261026/candidate_two_dc.py](../source/%E5%B5%8C%E8%B5%9B/amr_rescue_gmsk_candidate_20261026/candidate_two_dc.py) | 公共头尾参考的two-DC恢复实现；原始独立候选及后续复用来源 |
| 模型训练与NPU推理 | [source/FPGA_Work/rml24_fpga_ui_integration_20261031/shared_owner/npu_stream_shared.cpp](../source/FPGA_Work/rml24_fpga_ui_integration_20261031/shared_owner/npu_stream_shared.cpp) | 共享设备所有权的NPU流式推理源码；正式监管器实际调用的共享工作进程，其外部二进制身份另有核验记录 |
| 模型训练与NPU推理 | [source/AMR_Rescue_20261025/npu_stream.cpp](../source/AMR_Rescue_20261025/npu_stream.cpp) | 原始NPU流式推理服务实现；保留兼容身份核对，不代表最终默认直接调用此进程 |
| FPGA与PS/PL接口 | [source/嵌赛/rml24_test_readiness_20261030/fpga/scan_xrt.cpp](../source/%E5%B5%8C%E8%B5%9B/rml24_test_readiness_20261030/fpga/scan_xrt.cpp) | FPGA频谱回读驱动参考；监管器实际传入外部scan_xrt路径，其构建与版本还须结合部署记录 |
| FPGA与PS/PL接口 | [source/FPGA_Work/smartscan_prefetch_fix3_20261031/fpga/npu_base/run_impl_route.tcl](../source/FPGA_Work/smartscan_prefetch_fix3_20261031/fpga/npu_base/run_impl_route.tcl) | 集成FPGA布局布线流程入口；需先恢复原目录并准备商业IP与工具环境 |
