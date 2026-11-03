# 部署变更集

覆盖层包含 12 个部署文件：

1. `rml24_final/board_runtime/standalone_receiver.py`：扫描丢锁双条件滞回。
2. `rml24_final/runtime/scan_lock_policy.py`：独立、可测试的扫描锁定策略。
3. `rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py`：保留冻结的八段平均接收器身份。
4. `rml24_final/board_runtime/repeat_mean_candidate.py`：冻结候选副本。
5. `rml24_final/board_runtime/run_repeat_mean_gapfix1.sh`：独立运行入口。
6. `rml24_final/runtime/ui_event.py`：从同一恢复张量生成星座、频谱和诚实的模型域测量值。
7. `ui_sw/ui_render.hpp`：第五页几何、频率状态字段和不遮挡标题的数字键盘。
8. `ui_sw/ui_render.cpp`：五页视觉层级、测量仪表盘、两模式、四频率字段和数字键盘。
9. `board_package/touch_mode_control.hpp`：移除用户层 AutoLock 映射。
10. `board_package/frequency_control.hpp`：MHz 编辑、校验、命令、ACK 同步和离页取消。
11. `board_package/ui_state_map.hpp`：将可信的恢复 IQ 测量值接入参数页。
12. `board_package/board_ui_live_rml24_final.cpp`：触控、控制 socket、生产者 readback 和模态编辑器接线。

未包含模型、two-DC、公共帧、门限、FPGA 位流、systemd 文件或历史 RF 结果。

## UI2 设计约束

- 第一页只突出 Top-3 分类。
- 第二页只显示可从当前恢复 IQ 或接收配置直接得到的值。
- `RECOVERED RMS`、`RECOVERED PEAK` 明确属于模型域，不冒充 ADC counts/dBFS。
- 频谱中位数使用 `dB rel`，占用带宽和中心偏移明确标记 `EST`。
- 不显示未经校准的 SNR。
- 第五页仅保留 `FIXED` 与 `BAND SCAN`；自动锁定仅作为扫描内部状态。
- 数字键盘不覆盖标题和值；离开第五页会取消未提交草稿。
