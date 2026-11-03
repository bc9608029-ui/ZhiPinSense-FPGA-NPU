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
10. `board_package/frequency_control.hpp`：MHz 十进制编辑（精确转整数 Hz）、校验、命令、ACK 同步和离页取消。
11. `board_package/ui_state_map.hpp`：将可信的恢复 IQ 测量值接入参数页。
12. `board_package/board_ui_live_rml24_final.cpp`：触控、控制 socket、生产者 readback 和模态编辑器接线。

未包含模型、two-DC、公共帧、门限、FPGA 位流、systemd 文件或历史 RF 结果。

## A 线交付级收尾新增（2026-10-29，非部署覆盖层，仅诊断/预检）

1. `docs/DEPENDENCY_IDENTITY.md`：`standalone_receiver.py`（4d35cf5e）全部 import →
   实际导入路径 → 来源（覆盖层/BASE）→ 完整 SHA256 → 溯源性质（独立 vs 循环复制）身份表。
2. `scripts/preflight_deploy.py`：部署树 fail-closed 预检（缺文件=rc1、冻结 SHA 不符=rc2、
   expect 不符=rc3、用法=rc4）；四个 BASE 依赖只测存在并标记「待板端核验」，不自动接受任意 SHA。
3. `scripts/board_collect_dep_sha.sh`：板端仅采集四个 BASE 依赖实测 SHA（不自动接受），供人工
   对照身份表后写 `--expect` 清单严格复验。

以上三项不改变模型、two-DC、平均策略、单目标 UI 或任何冻结部署文件。

## UI2 设计约束

- 第一页只突出 Top-3 分类。
- 第二页只显示可从当前恢复 IQ 或接收配置直接得到的值。
- `RECOVERED RMS`、`RECOVERED PEAK` 明确属于模型域，不冒充 ADC counts/dBFS。
- 频谱中位数使用 `dB rel`，占用带宽和中心偏移明确标记 `EST`。
- 不显示未经校准的 SNR。
- 第五页仅保留 `FIXED` 与 `BAND SCAN`；自动锁定仅作为扫描内部状态。
- 数字键盘不覆盖标题和值；离开第五页会取消未提交草稿。
