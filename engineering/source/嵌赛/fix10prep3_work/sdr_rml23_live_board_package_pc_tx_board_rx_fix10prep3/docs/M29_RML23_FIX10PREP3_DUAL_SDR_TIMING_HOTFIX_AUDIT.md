# fix10prep3 双 SDR 分数时序与 TX-off 等待修复审计

## 范围与当前状态

本增量直接处理真实双 SDR BPSK/4ASK 烟测暴露的两个阻塞项：

1. BPSK 已成功发射与捕获，CFO 有限且在无歧义范围内，但宽带 ZC 前导的整数样点相关仅为
   `0.720230`，低于原门限 `0.9`；同帧窄带 payload training 相关为 `0.989795`。
2. PC 在第一帧 `STOPPED` 后处于 TX 已关闭的 `WAIT_PREPARE`，但仍将板端恢复/分类超过
   2 秒误判为协议超时，导致第二帧未能进入 PREPARE。

这不是模型故障：失败发生在 NPU 前的 RF 恢复门禁，本次不改模型、权重、标签、24→23 映射或分类基线。

离线修复已完成并通过 host 全量回归；真实双 SDR 结果仍需用户重新上板确认。在用户板测前，
不写 `SMOKE-PASS` / `RF_PASS` / `RF_PATH_PROVEN` / `PROJECT_COMPLETE` / `FINAL_*`。

## 修复 1：双 SDR 专用分数样点时序对齐

文件：`board_package/iq_dual_sdr_coarse_cfo_recovery.hpp`

- 仅在 fix10 双 SDR coarse-CFO wrapper 内生效，不改红线核心 `iq_rf_sync_recovery.hpp`。
- 粗 CFO 去旋后，用前导估计 `[-0.5,+0.5]` 样点内的剩余分数时延；不使用调制标签或分类结果。
- 采用确定性两级网格搜索（1/32 粗搜、1/512 细搜）和半径 12 的 Lanczos-windowed sinc 插值。
- 对齐后再调用原 `iqrfrec::estimate/apply`；`min_corr=0.9` 及 residual/clip/CFO/SRO 门限均不变。
- 日志新增 `fractional_timing_samples` / `fractional_corr_before` /
  `fractional_corr_after`，便于板测判断是否真正恢复了前导相关。

合成测试注入 `0.4375` 样点延迟，确认：修复前整数网格相关 `<0.9`；估计误差
`<=0.03` 样点；对齐探针相关 `>=0.95`；最终仍须通过原 `0.9` 门限；恢复 payload 相关
`>=0.98`。

## 修复 2：仅在 TX-off WAIT_PREPARE 容许板端计算空闲

文件：`host_tools/fix10_tx_protocol.py`

- 区分“下一帧 header 一个字节都未到”与“部分 header/body 后超时”。
- 只有 `WAIT_PREPARE` 可以在空 header 超时后继续轮询；该状态中 TX 已停止并恢复。
- `WAIT_START` / `WAIT_CAPTURED`、部分 header、部分 body 仍按原 2 秒规则 fail-closed。
- 独立 TX watchdog 不变，清理路径仍在任何退出时停止 TX。

## 离线验证

- `test_iq_dual_sdr_23class_fix10`: `29/29 PASS`。
- Python protocol tests: `38/38 PASS`，覆盖 TX-off 长计算等待、部分 header 超时拒绝、
  `WAIT_START` 超时仍拒绝。
- `host_tests/build_host_tests.sh` + `host_tests/run_tests.sh`: `ALL HOST TESTS PASSED`。
- Windows radioconda `pc_tx_sdr_fix10.py --self-test`: `27/27 PASS`（含 WSL burst tool self-check）。

## 板测验收

本轮产物需重新上传并重新编译板端，PC 也必须从同一轮新工作树启动。必须同时满足：

- BPSK 和 4ASK 均进入 `PREPARED -> READY -> CAPTURED -> STOPPED`。
- `fractional_corr_after >= fractional_corr_before`，且最终 `training_corr >= 0.9`。
- `cfo_finite=1` 且 `cfo_in_range=1`。
- `scored=2`, `rf_excluded=0`, `prediction_agreement=2/2`。
- `tx_restore_ok=1`, `rx_restore_ok=1`, `negative_control=PASS`。

若仍失败，按日志中第一个真实失败项停止；不降低门限、不改 baseline、不换样本。
