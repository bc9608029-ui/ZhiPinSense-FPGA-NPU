# M29 RML24 fix10class24-singlesdr-ab1 审计 — 单SDR自发自收严格A/B对照

状态：**`M29-RML24-FIX10CLASS24-SINGLESDR-AB1-READY-FOR-BOARD-TEST`**
（最高允许状态；**禁写 RF_PASS / SMOKE_PASS / PROJECT_COMPLETE / FINAL_* / RUNTIME-INTEGRATED**）

本任务是**测量**，不是回归 PASS。单 SDR 对照用于隔离「双 SDR 特有链路」是否为
full24-accuracy1 那 18/24 结果的主因；runner 报告 coverage / gated accuracy /
end-to-end accuracy 三项，第四项 forced raw24 accuracy 板端只打印 `PENDING`，数值由
离线汇总脚本产出并标注 `HYBRID_BOARD_GATED_PLUS_HOST_FORCED`。

---

## 1. 为什么做

Phase A（full24-accuracy1）已证明：双 SDR 链路上，0.100 门旁路也只 18/24（gated 内
10/15，5 个确定性同族升阶错误来自板端 NPU）。但**至今所有 24 类 BF16 真实 RF 测试都
是双 SDR**（PC-TX/板-RX，独立时钟 + 双模拟前端 + TCP 控制）。单 SDR 自发自收那条线
（`iq-rf-loopback-23class-fix9r`）是 **23 类**，且走旧单 SDR `estimate`+`apply` 路径。

本任务补一个**和双 SDR 同恢复链**的单 SDR 对照。严格 A/B 铁律（用户强制）：单 SDR 捕获
**逐字复用** rxrecovery1 双 SDR runner 的 `recover_payload_with_coarse_cfo`、分数定时、
wide-linear 补偿、最多 3 次有界重捕获、最终捕获选择规则。**唯一允许差异**：TX 和 RX 由
两台 SDR 变为同一台 SDR、本地 TX 代替 PC TX（TCP 控制→本地 cyclic 发射）。单 SDR 共享
时钟，coarse CFO 自然≈0，但**代码路径与双 SDR 完全一致**（不退回 `estimate`+`apply`）。

## 2. 复用点（全部探明并落实）

- **恢复核心**：`iqdual23fix10::recover_payload_with_coarse_cfo(rx, rec_cfg, payload_tx_scale)`
  （`board_package/iq_dual_sdr_coarse_cfo_recovery.hpp`），与双 SDR runner 调用**完全相同**。
  内部含 coarse-CFO 预旋转、分数定时（Lanczos sinc）、三趟 `iqrfrec::estimate`、`iqrfrec::apply`
  （含 wide-linear 补偿）。`rec_cfg` 与双 SDR runner 逐字段一致：`min_corr=0.9` /
  `max_residual=0.100` / `max_cfo_hz=fine_cfo_range_hz()` / `max_sro_ppm=30.0` /
  `search_limit=0` / `payload_tx_target_rms=target_rms`。
- **有界重捕获 + 最终捕获选择**：逐字复现双 SDR runner 的 `for(;;) ++capture_attempts`
  循环；`retry = !stop && rf_verdict=="RF_DISTORTS_IQ" && should_retry_payload_training_capture(...)`
  （≤`kPayloadTrainingCaptureMaxAttempts=3`）；**最终捕获 = 最后一次 attempt 的 `ccr`**。
- **fidelity gate 顺序**（用户三处逐字修正之一）：负控制 fail/clip → `RF_RX_CLIPPED` →
  `!ccr.rec.valid`→`failure_rf_verdict(failure)` → `!cfo_in_range`→`RF_CFO_OUT_OF_RANGE` →
  否则 `RF_PRESERVES_IQ`；`gate_ok = (rf_verdict=="RF_PRESERVES_IQ")`。
- **TX/RX 工作态写后读回 fail-closed**：`set_sample_rate(2560000)` 同写 RX+TX（不存在
  `set_tx_sample_rate`，编译期保证）；分别 `get_rx_sample_rate()`/`get_tx_sample_rate()` 读回
  （差 ≤5Hz）；RX LO/BW/gain(mode=="manual"+35dB)、TX LO/BW/atten/loopback 均写后读回。
- **单 SDR 物理传输**：`board_package/iq_rf_loopback_transfer_24class_bf16_fix10.hpp` 只负责
  单次 `PlutoTx prepare()`（loopback=0 + `confirm_safe_rf_path` + TX atten ≤ -40 双层检查）→
  `start_cyclic()` → RX 冲刷 → `capture_contiguous` → `stop()`；`cfg.rx_gain_db=35` 显式覆盖
  `prepare()` 第 3 步的默认 10 dB，prepare 后读回确认 manual/35dB fail-closed。
- **退出清理（用户三处逐字修正之二）**：所有退出路径（正常/early-return/异常/用户停）
  `tx.stop()` → 确认 `tx_running()==false` → `DeviceStateGuard::restore()` → 记录 restore 结果；
  RAII scope guard + runner 末尾显式同一次 `guard->restore()` 产出 `tx_restore_ok`/`rx_restore_ok`
  （二者注明来自同一设备恢复）。
- **Canonical TX burst**：`fix10canonical::buildTxBurstFromFrozen(path, complex_count, expect_sha, target_rms)`
  产出与 PC-TX 字节一致的 canonical burst；单 SDR 直接发射 `expected.burst`，`expected.tx_scale`
  传进 `recover_payload_with_coarse_cfo` 的 `payload_tx_scale`。
- **clean24_smoke manifest**：`load_frozen_iq(dir, "radioml-d2-2p56m")`；full24 读全部 24 行，
  short2 按 modulation 名过滤 BPSK+4ASK。
- **门拒强制分类**：`host_tools/replay_fix10class24_failed_rx_force_classify.sh` 导出
  `model_input_f32le.bin` + `forced_recovery.json` → `icraft-run --backends Host` 冻结 BF16 Host
  推理（≥2 前向）→ raw24 预测；层 `HOST_BF16_FORCED_CLASSIFICATION`，非板端 NPU。

## 3. 四指标口径（报告同时给出）

| 指标 | 定义 | 来源 |
|---|---|---|
| coverage | gated 样本数 / total | runner 直接统计 |
| gated accuracy | gated 内 label_correct / gated 数 | runner 直接统计 |
| end-to-end accuracy | gated 内 label_correct / total（门拒计 0） | runner 直接统计 |
| forced raw24 accuracy | (gated 内正确 + 门拒经冻结 BF16 Host 强制分类判对) / total | runner 打印 `PENDING`；离线汇总脚本产出，标注 **`HYBRID_BOARD_GATED_PLUS_HOST_FORCED`**（用户三处逐字修正之三） |

## 4. 红线（逐字节不变）

- 15 个红线头（恢复核心 `iq_rf_sync_recovery.hpp` + `iq_dual_sdr_coarse_cfo_recovery.hpp`、
  双 SDR runner `iq_pc_tx_board_rx_24class_bf16_fix10.hpp`、canonical 帧 3 组件、transfer 状态机、
  raw24/baseline 合同头）**逐字节等于 rxrecovery1 FULL 基线**。
- BF16 模型 json `28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42` /
  raw `c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151` / checkpoint `96cd25f8…`。
- 24 类标签序、`kPayloadTrainingResidualMax=0.100`、TX 安全上限 `--tx-atten<=-40`、
  canonical 3 CI16、clean24_smoke 24 文件 + manifest、baseline、rml23_merged/rml24_raw 合同。
- 旧 phase（尤其 `iq-rf-loopback-23class-fix9r`、`iq-pc-tx-board-rx-24class-bf16-fix10`）行为不变。

## 5. 改动集（相对 rxrecovery1 FULL 基线 `6fd93f78…`，纯增量，无删除）

新增 9：
- `board_package/iq_rf_loopback_transfer_24class_bf16_fix10.hpp`
- `board_package/iq_rf_loopback_24class_bf16_fix10.hpp`
- `host_tests/test_iq_rf_loopback_24class_bf16_fix10.cpp`
- `host_tests/test_fix10class24_singlesdr_ab1_forced.py`
- `scripts/aggregate_fix10class24_singlesdr_ab1_forced.py`
- `scripts/run_fix10class24_singlesdr_ab1.sh`
- `scripts/package_fix10class24_bf16_singlesdr_ab1.py`
- `docs/M29_RML24_FIX10CLASS24_SINGLESDR_AB1_AUDIT.md`（本文件）
- `docs/M29_RML24_FIX10CLASS24_SINGLESDR_AB1_BOARDTEST_NOTE.md`

修改 4（纯增量接线）：
- `board_package/gate9_phase.hpp`（`valid_phase()` 加 1 分支）
- `board_package/board_gate9_full_chain_rml23.cpp`（`#include` + 新 wrapper + error 文本 + dispatch）
- `host_tests/build_host_tests.sh`（注册新测编译）
- `host_tests/run_tests.sh`（注册新测运行）

## 6. host 测试结果（离线，不碰板）

- `bash host_tests/build_host_tests.sh` → **BUILD_RC=0**（含新 `test_iq_rf_loopback_24class_bf16_fix10`）
- `bash host_tests/run_tests.sh` → **RUN_RC=0 / ALL HOST TESTS PASSED**（全套回归 + 新测，旧 phase 不破）
- 新 C++ 测 `test_iq_rf_loopback_24class_bf16_fix10`：**36 checks / 0 fail**（phase 解析 7 +
  manifest 覆盖 4 + 模型/标签身份 8 + baseline SHA 3 + TX burst 字节一致 10 + 天花板/读回
  fail-closed 3 + 采样率双写 1）
- 新 Python 测 `test_fix10class24_singlesdr_ab1_forced.py`：**12/12**（四指标合并 4 + 板脚本拓扑 7 + 接线 1）
- 汇总脚本自测 `--self-test`：**25 checks / 0 fail**（0/3/24 门拒三档，证明不硬编码 20）
- 红线 diff（`diff -rq` 基线 vs 新树）：源文件层面**恰好** 4 修改 + 9 新增；模型/标签/contract/
  canonical/恢复核心/0.100 门/双 SDR runner 逐字节未变；其余差异仅 `__pycache__`/`.pytest_cache`/
  `results`/`dist`（构建产物，打包时排除）。

## 7. 板测手册

**前提**：板端已部署 rxrecovery1 FULL（`6fd93f78…`）；解压本 PATCH 覆盖即可（flat 路径）。
构建 + 运行前先确认 `LIBIIO_ROOT=/opt/sdr/libiio-0.26`（`run_gate9_rml23.sh` 已透传）。

**板端命令（由用户串口执行，我不碰板/不操作 SDR）**：

```bash
# 1) 短测（BPSK + 4ASK 两样本），先验门禁：
bash scripts/run_fix10class24_singlesdr_ab1.sh --rx-uri=usb:1.3.5 --mode=short2

# 2) 全 24 类：
bash scripts/run_fix10class24_singlesdr_ab1.sh --rx-uri=usb:1.3.5 --mode=full24

# 3) 若 full24 达 24/24，再重复两轮（共 3 轮）确认可复现：
bash scripts/run_fix10class24_singlesdr_ab1.sh --rx-uri=usb:1.3.5 --mode=full24
bash scripts/run_fix10class24_singlesdr_ab1.sh --rx-uri=usb:1.3.5 --mode=full24
```

判据：runner 打印 coverage / gated_accuracy / end_to_end_accuracy 三数值 + 每样本
`FIX10CLASS24_BF16_SINGLESDR_*` 标记 + 聚合行；`forced_raw24_accuracy=PENDING`。

**forced raw24 离线合并（host，icraft-run.exe，冻结 BF16 Host）**：

```bash
python3 scripts/aggregate_fix10class24_singlesdr_ab1_forced.py --phase aggregate \
    --out-dir '<OUT_DIR>' --clean24-dir clean24_smoke \
    --baseline baselines/clean24_smoke_raw24_bf16_baseline.tsv \
    --icraft-run /path/to/icraft-run.exe --model-dir model_rml24_bf16 \
    --force-classify-tool host_tools/replay_fix10class24_failed_rx_force_classify.sh
```

输出层 `HYBRID_BOARD_GATED_PLUS_HOST_FORCED`，门拒部分层 `HOST_BF16_FORCED_CLASSIFICATION`。

## 8. 停止条件

PATCH 包生成校验通过 + host 测试通过 + 板端构建/运行命令就绪 + 不碰板不操作 SDR +
等用户串口执行 → 暂停汇报。**不写任何 PASS 类结论。**
