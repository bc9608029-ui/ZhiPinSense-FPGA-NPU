# M29 RML23 Stage H-F / Route F — IQ RF 回环（fix7）审计

**状态**：`M29-RML23-IQ-RF-LOOPBACK-READY-FOR-BOARD-TEST`（未取得板端证据前不变；不写任何
`RF_PASS` / `RF_PATH_PROVEN` / `PROJECT_COMPLETE` / `FINAL_*` / `BOARD_TEST_PASS`）。
**基线**：`sdr_rml23_live_board_package_iq_digital_loopback_fix6.tar.gz` `713c93b4…`（540 文件）。
**本轮工件**：独立补丁 `sdr_rml23_live_iq_rf_loopback_fix7_patch.tar.gz` + 合并全量
`sdr_rml23_live_board_package_iq_rf_loopback_fix7.tar.gz`（fix6 全量 + fix7）。精确路径/字节/
文件数/manifest 行数/64-hex SHA 见 `dist/RML23_IQ_RF_LOOPBACK_FIX7_DELIVERY.txt`。

---

## §1 背景与判责边界

fix5/fix6 已把**数字**回环（Route E）推到全周期同步 + 尺度无关保真 + 分类窗口选择的
READY-FOR-BOARD-TEST 状态。fix7 是 **Route F**：ADALM-Pluto **物理 TX→RX 外部射频自回环**，
加上一条**非训练**的 Route D2 4ASK 消融，以及一条**内存/总闸**修复。三个子任务相互隔离：

| 子任务 | 内容 | 判责边界 |
|---|---|---|
| **A** | 内存（逐文件大缓冲释放）+ 总 GATE 折叠 M22/分类 | 不提高/不关闭任何 RSS 阈值；accuracy 恒为测量不判 PASS |
| **B** | `--phase=iq-rf-loopback` 物理 RF 自回环 | RF 保真仅板端建立；host 测试永不把 `RF_PATH_NOT_PROVEN` 升级 |
| **C** | Route D2 非训练 4ASK 消融 | 只判重构证据；不能救回 4ASK 即诚实结论 `NON_RETRAINING_4ASK_FIX_NOT_PROVEN` |

物理 RF 模式与既有数字回环**完全独立**：不复用 `iq-digital-loopback` 名称，不改动 Route E 数字回环的
任何安全行为。数字回环（loopback=1）与 RF（loopback=0）语义互不侵入。

---

## §2 三个子任务：要求 → 实现

### Task A — 内存 + 总 GATE 修复

**要求**：
1. 逐文件大缓冲（`aligned_rx` 等）必须释放，保留的 summary 只含标量 + 短 SHA，避免 240 文件累计
   ~51 MiB RSS 增长触发 M22 RSS-growth 闸；
2. 总 GATE 必须在 fidelity / 分类 / M22 / restore 任一失败时 FAIL（M22 FAIL 必须传播到总 GATE FAIL）；
3. 不得提高或关闭任何 RSS 阈值。

**实现**：
- `board_package/iq_rf_loopback_report.hpp::push_rf_file_summary()`（RF 侧）与
  `board_package/iq_digital_loopback_runner.hpp::push_file_summary()`（数字侧，新增）：
  `std::vector<std::int16_t>().swap(pf.rf.sync.aligned_rx)` / `std::vector<std::int16_t>().swap(pf.sync.aligned_rx)`
  在 move 前把 2P int16 大块换成空向量（同时释放容量），保留的 `RfPerFileResult` / `PerFileResult`
  只剩标量 + 短 SHA。逐文件循环复用同一被释放的块，全程 RSS 有界。
- 数字 runner 的 5 处 `rep.files.push_back(std::move(pf))` 全部换成 `push_file_summary(rep.files, std::move(pf))`
  （`iq_digital_loopback_runner.hpp` 505/514/584/600/704 行）；RF runner 的两轮（校准/保留）都用
  `push_rf_file_summary`。
- `iq_rf_loopback_runner.hpp::RfRunReport` 新增 `classification_ok`（fix7 Task A 总闸）：
  `classification_ok = classification_verdict ∉ {RF_AMPLITUDE_NOT_CALIBRATED,
  INVALID_DUE_TO_FIDELITY_GATE, INSUFFICIENT_EVIDENCE}`；`functional_pass = infra_ok && fidelity_ok &&
  classification_ok`。accuracy（`classification_verdict` 由 `iqdloop::classification_verdict(...)` 算出）是
  纯测量，**永不**因为 accuracy 低于某值而判 FAIL。
- `board_gate9_full_chain_rml23.cpp::run_iq_rf_loopback()`（2680-2692 行）折叠 M22：
  `m22_ok = finish_m22_runtime("iq-rf-loopback", ...)`，`pass = final_gate_pass(rep.functional_pass && m22_ok,
  rep.restore_ok, detail)`。M22 FAIL → 总 GATE FAIL。

### Task B — Route F 物理 RF 自回环

**要求**（逐条落地位置）：
1. 新 phase `--phase=iq-rf-loopback`（不复用 `iq-digital-loopback`）——`gate9_phase.hpp` 新增匹配，
   `board_gate9_full_chain_rml23.cpp` 2994-2995 行新增分发；
2. `loopback=0` 且 readback 确认 —— `iq_rf_loopback_transfer.hpp` 140-147 行：`prepare()` 后显式
   `get_loopback()`，`!=0` 直接 throw（fail-closed）；
3. `--rf-path=direct-cable` 强制 —— `iq_rf_loopback_runner.hpp` 157-161 行：非 `direct-cable` 拒绝发射；
4. `--tx-atten=-40`（默认即 `kSafeTxCeilingDb` 天花板）—— runner 143 行默认 -40.0，`PlutoTx::prepare()`
   的 -40 dB 天花板与 readback 校验仍生效，程序**不得**自动提高 TX 功率；
5. `--rx-gain=<value>` 手动增益 —— runner 142 行 `--rx-gain` 默认 10.0，经 `TxConfig.rx_gain_db` 传给
   `PlutoTx::prepare()` 手动设置；
6. 50Ω SMA 同轴直连、无天线/无外部功放 —— `transfer_one_file_rf` 仅走 `confirm_safe_rf_path=true` 的
   外部 RF 路径，BUFFER 日志固定 `antenna=none coax=direct-cable ensm=not_managed_by_this_code`；
7. RAII 保存/恢复全部设备参数 —— `DeviceStateGuard`（runner 250-252 行），restore 幂等（681-685 行），
   恢复失败 fail-closed；
8. TX-off 负对照先于 TX-on —— `transfer_one_file_rf` 104-116 行：`tx_stop()` → `recreate_rx_buffer()` →
   单次连续 `noise_complex` 采集，作为每文件噪声底证据；
9. 每文件记录 —— `IQ_RF_LOOPBACK_TX_VERIFY / TX_DMA_PAYLOAD / NEGATIVE_CONTROL / REFILL / BUFFER /
   NOISE_FLOOR / fidelity / SYNC_ORIGIN` 各一行 + `RfPerFileResult` 全字段；
10. RF 保真 token（观测）—— `iq_rf_loopback.hpp::rf_fidelity_verdict()`（见 §4 判据序）；
11. 同步用 fix6 全周期 FFT 圆相关 —— `measure_rf_fidelity` 复用 `iqdloop_sync::measure_fidelity_fix5`，
    绝不用有界延迟搜索；
12. 分类**不得**用逐文件参考 TX 做 oracle 校正 —— runner 553-579 行：分类输入只用
    `apply_global_gain_to_stream`（**唯一**全局增益），`pf.rf.sync.gain_count/phase_deg` 逐文件最优拟合只
    用于测量/校准收集，从不进分类；
13. RF 幅度校准仅一个全局固定增益，来自独立校准序列 —— `--rf-calib-count=N` 前 N 文件做校准
    （runner 494-517 行），`estimate_global_gain`（幅度中位数 + 相位圆均值）估计，held-out 用该全局增益；
14. 物理 RF 模式必须明确关闭内部数字回环并验证 readback loopback=0 —— 见第 2 条。

**RF 保真判据序**（`iq_rf_loopback.hpp::rf_fidelity_verdict`，A→G 严格顺序）：
`INSUFFICIENT_EVIDENCE`（rx_complex < 最小）→ `RF_CAPTURE_TOO_SHORT` → `RF_RX_ALL_ZERO` →
`RF_RX_TOO_LOW`（SNR < 6 dB）→ `RF_RX_CLIPPED` → `RF_SYNC_NOT_FOUND`（origin Ambiguous）→
`RF_DISTORTS_IQ`（corr < 0.9）→ `RF_PRESERVES_IQ`（corr ≥ 0.9 ∧ normalized_residual ≤ 0.05 ∧ 无削顶 ∧
nmse_evm_consistent）。runner 在此前把 loopback-readback / TX-DMA / negative-control 三个基础设施闸折在前：
`loopback_readback!=0 → RF_PATH_NOT_PROVEN`、`!tx_dma_payload_ok → RF_TX_DMA_PAYLOAD_MISMATCH`、
`!negative_control_ok → RF_NEGATIVE_CONTROL_FAIL`（runner 448-456 行）。

### Task C — Route D2 非训练 4ASK 消融

`scripts/analyze_route_d2_4ask.py`（新，纯 Python stdlib，不训练、不碰 NPU、不跑分类、不判 accuracy PASS）：
- **D0** 基线：逐文件 RMS 归一（`scale = DEFAULT_RMS_TARGET / signal_rms`）；
- **D1**：单一全局 `K`（`scale = K`）；
- **D2**：D1 + 保留信号自身 DC（DC 与 AC 分离，int16 路径只载 AC，`rec_scale = ac_rms · 2048/K` 把 AC 的
  int16 RMS 映射回 AC 的模型域 RMS，DC 在模型域恢复）；
- **D3**：edge（zero/reflect）× guard（768/832/896）网格扫描，验证 resample/quant/window 边界效应；
- **全局 K 仅由无标签重构误差/量化利用率/削顶率**在固定校准子集上选择，独立 holdout 上固定不变；
- 每类 4×60（D 路 vs D2 路逐类对比）结果写入 JSON；不能救回 4ASK 即
  `NON_RETRAINING_4ASK_FIX_NOT_PROVEN`，绝不改标签、不强制类别、不做 4ASK 专用规则。
- Route F 板端 A/B 测试 = D 路与 D2 路交织（见 §7 板端复测）。

---

## §3 文件差异（相对 fix6 `713c93b4…` 基线）

**6 改**：
| 文件 | 变更 |
|---|---|
| `board_package/board_gate9_full_chain_rml23.cpp` | `--phase=iq-rf-loopback` 分发 + `run_iq_rf_loopback` 包装 + M22 折叠 |
| `board_package/gate9_phase.hpp` | phase 表新增 `iq-rf-loopback` |
| `board_package/iq_digital_loopback_runner.hpp` | 新增 `push_file_summary` 内存 sink，5 处 push 替换 |
| `sdr_adapter/pluto_device.hpp` | `get_loopback` 支持 `loopback_readback_override` + RF 回波测试钩子 |
| `host_tests/build_host_tests.sh` | 新增 `test_iq_rf_loopback` 构建（链接 `pluto_tx.cpp`） |
| `host_tests/run_tests.sh` | 新增 `test_iq_rf_loopback` 运行 |

**8 新**：
| 文件 | 内容 |
|---|---|
| `board_package/iq_rf_loopback.hpp` | 纯逻辑：负对照测量 + RF 保真判据 + 全局增益估计/施加 |
| `board_package/iq_rf_loopback_report.hpp` | 每文件 summary 类型 + `push_rf_file_summary` 内存 sink |
| `board_package/iq_rf_loopback_transfer.hpp` | 每文件物理 RF 传输（板端/host 逐字共享） |
| `board_package/iq_rf_loopback_runner.hpp` | 板端编排（校准 + held-out 分类 + 三判决分离 + 总闸） |
| `host_tests/test_iq_rf_loopback.cpp` | host RF 测试（48 检查） |
| `scripts/analyze_route_d2_4ask.py` | Route D2 非训练 4ASK 消融 |
| `scripts/package_iq_rf_loopback_fix7.py` | 打包器（dependency closure fail-closed） |
| `docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX7_AUDIT.md` | 本审计 |

**红线合规**：无模型/标签映射/NPU 二进制/RTL/XDC/位流/Flash 改动；不重训/不微调；不按真实标签选缩放；
不用逐文件 oracle 幅度归一；不新增 4ASK 专用分类规则；不修改任何 fix6 工件（fix7 全部为新文件）；物理 RF
模式明确关数字回环并 readback 验证；-40 dB 天花板不变；现有数字回环安全行为未受影响；未取得板端证据前
状态 READY-FOR-BOARD-TEST；API 未连接/未操作板卡。

---

## §4 核心代码位置

- 内存 sink：`iq_rf_loopback_report.hpp:70-74`、`iq_digital_loopback_runner.hpp:166-174`
- RF 保真判据：`iq_rf_loopback.hpp:126-146`；负对照：`iq_rf_loopback.hpp:83-122`；全局增益：
  `iq_rf_loopback.hpp:170-223`
- 物理 RF 传输：`iq_rf_loopback_transfer.hpp:77-189`（loopback readback 闸 140-147 行，负对照 104-116 行，
  TX DMA payload SHA 152-154 行，stale flush 157-164 行，capture≥2·周期+margin 167-180 行）
- 板端编排：`iq_rf_loopback_runner.hpp:128-747`（校准轮 494-517，held-out 分类 519-656，三判决分离 691-710）
- 分发 + M22 折叠：`board_gate9_full_chain_rml23.cpp:2645-2695, 2994-2995`
- host 测试：`host_tests/test_iq_rf_loopback.cpp`（12 组 44 检查）

---

## §5 离线验证（本轮，不碰板）

1. `host_tests/build_host_tests.sh` 全绿（含新增 `test_iq_rf_loopback` 链接 `../sdr_adapter/pluto_tx.cpp`）；
2. `host_tests/run_tests.sh` → `ALL HOST TESTS PASSED`（新增 `test_iq_rf_loopback` 48/0）；
3. `host_tests/syntax_check.sh` → `gate7/gate9/gate10/gate9_rml23: syntax OK`；
4. `scripts/analyze_route_d2_4ask.py` self-test 7/7，合成演示 D0/D1/D2/D3 + JSON，结论
   `RECONSTRUCTION_IMPROVED_BY_ROUTE_D2_NON_RETRAINING`；
5. 打包器 `audit_dependency_closure` OK（所有改动头文件已列入 `ROUTE_F_FIX7_FILES`，不会再静默回退到
   fix6 基线）；两份 tarball 确定性重打包一致；独立解包 `sha256sum -c` 全 OK。

---

## §6 板端复测（用户执行；本审计不写死 ip、不强制）

```
第一步（物理 RF 回环，先小规模校准 + 负对照观测）：
./scripts/run_gate9_rml23.sh --phase=iq-rf-loopback --center=2400000000 --rx-gain=10 \
  --tx-atten=-40 --rf-path=direct-cable --rf-calib-count=8 --input-kind=generated-2p56m \
  --frozen-dir=DIR > /root/rml23_route_f_fix7.log 2>&1
```
预期观测：`IQ_RF_LOOPBACK_FORMAT dir=tx/rx`、`NEGATIVE_CONTROL capture_ok=1`、
`BUFFER loopback=0 tx_atten_readback_db≈-40`、每文件 fidelity token、`CALIBRATION valid=1`、held-out
分类 `classification=SKIPPED reason=no_global_calibration_gain` 仅当校准为空、否则全局增益后分类。
`RF_PRESERVES_IQ` 仅由板端运行建立，host 测试永不升级 `RF_PATH_NOT_PROVEN`。

第二步（Route F 的 D vs D2 A/B 交织，判 D2 非训练 4ASK 是否成立）：
由 Route D2 消融脚本在板端 recovered 输出上复算，D 路与 D2 路交织；仅当保真门全达 `RF_PRESERVES_IQ`
才把分类判据作为测量记录，绝不判分类修复完成。

---

## §7 交付

2 工件（独立补丁 + 合并全量），SHA256SUMS manifest + 独立解包 `sha256sum -c` 校验，精确
路径/字节/文件数/manifest 行数/64-hex SHA 见 `dist/RML23_IQ_RF_LOOPBACK_FIX7_DELIVERY.txt`。
历史包（fix6 `713c93b4…` 及更早全部）原样保留。
