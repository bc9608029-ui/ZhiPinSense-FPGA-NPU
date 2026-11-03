# 变更集

部署叠加共 10 个文件：

1. `rml24_final/board_runtime/standalone_receiver.py`：双条件丢锁滞回。
2. `rml24_final/runtime/scan_lock_policy.py`：独立可测策略。
3. `rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py`：保留已冻结八段平均并绑定新接收器 SHA。
4. `rml24_final/board_runtime/repeat_mean_candidate.py`：冻结候选副本。
5. `rml24_final/board_runtime/run_repeat_mean_gapfix1.sh`：独立运行入口。
6. `ui_sw/ui_render.hpp`：模式页几何和频率状态字段。
7. `ui_sw/ui_render.cpp`：两模式、四字段、数字键盘、扫描内部状态。
8. `board_package/touch_mode_control.hpp`：移除 AutoLock 触控映射。
9. `board_package/frequency_control.hpp`：MHz 编辑、校验、命令和 ACK 同步。
10. `board_package/board_ui_live_rml24_final.cpp`：触控/控制 socket/生产者 readback 接线。

没有包含模型、two-DC、公共帧、门限、FPGA 位流、systemd 文件或历史结果。
