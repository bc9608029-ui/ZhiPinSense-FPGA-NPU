# M29 RML23 Stage H-F / Route F — IQ RF 回环 fix8 审计

**状态**：`M29-RML23-IQ-RF-LOOPBACK-READY-FOR-BOARD-TEST`（未取得板端证据前不变；不写任何
`RF_PASS` / `RF_PATH_PROVEN` / `RF_PATH_PRESERVES` / `PROJECT_COMPLETE` / `FINAL_*` /
`BOARD_TEST_PASS`；sweep RC=0 ≠ 回环保真 PASS）。
**基线**：`sdr_rml23_live_board_package_iq_rf_loopback_fix7.tar.gz` `20d843c2…`（548 文件）。
**本轮工件**：独立补丁 `sdr_rml23_live_iq_rf_loopback_fix8_patch.tar.gz` + 合并全量
`sdr_rml23_live_board_package_iq_rf_loopback_fix8.tar.gz`（fix7 全量 + fix8）。精确路径/字节/
文件数/manifest 行数/64-hex SHA 见 `dist/RML23_IQ_RF_LOOPBACK_FIX8_DELIVERY.txt`。

---

## §1 背景与判责边界

fix7 已把 Route F 物理 RF 自回环 + Route D2 非训练 4ASK 消融推到 READY-FOR-BOARD-TEST。fix8 是
Route F 的**判责仪表加固 + 安全工作点扫描 + 冻结工件审计 + D-vs-D2 A/B 门禁**，六个子任务相互隔离：

| 子任务 | 内容 | 判责边界 |
|---|---|---|
| **A（四）** | 拆分 TX/RX 削顶证据，`RF_TX_CLIPPED`/`RF_RX_CLIPPED` 双 token | rails 由 `DataFormatInfo.bits` 推导，不硬编码 2047 |
| **B（五）** | 首次 TX-off 负对照瞬态修复（discard refill + 3 独立窗口） | 3 窗口异常 → `RF_NEGATIVE_CONTROL_UNSTABLE` fail-closed |
| **C（六）** | `--phase=iq-rf-loopback-level-sweep` RF 安全工作点扫描 | 无标签、无 NPU、无分类；削顶即拒绝该点 |
| **D（七）** | `audit_route_d_artifacts.py` Route D 冻结工件审计 | 只判 manifest/存在/符号链接/尺寸/SHA |
| **E（八）** | Route D2 非训练 4ASK `compute_verdict` 诚实结论 | holdout 4ASK 救回 ∧ 其余 3 类不退化，否则 NOT_PROVEN |
| **F（九）** | `iq_rf_loopback_ab.hpp` D-vs-D2 A/B 六门禁 | 任一门不过即 fail-closed 拒绝发射，纯门禁不判分类 |

物理 RF 模式与既有数字回环完全独立；`iq-rf-loopback-level-sweep` / `iq-rf-loopback-ab` 是全新
phase，不复用任何既有名称。

---

## §2 六个子任务：要求 → 实现

### Task A — 拆分 TX/RX 削顶（四）

**要求**：`SyncFidelityMetrics.clipped`（单一 bool）拆为 `tx_clipped`/`rx_clipped`/
`tx_clip_count`/`rx_clip_count`/`tx_peak`/`rx_peak`，rails 从 `DataFormatInfo.bits` 推导
（TX16→±32767/-32768，RX12→±2047/-2048）；`RF_TX_CLIPPED`/`RF_RX_CLIPPED` 双 token；
`RF_PRESERVES_IQ` 要求 `tx_clipped=0 ∧ rx_clipped=0 ∧ corr≥0.9 ∧ residual≤0.05 ∧ SNR≥6 dB ∧
sync origin 可解释 ∧ DMA 正确 ∧ loopback=0 ∧ 负对照有效 ∧ restore 成功`。

**实现**：
- `board_package/iq_digital_loopback_sync.hpp:320-325` 新增 `rail_positive(int bits)`/
  `rail_negative(int bits)`（`2^(bits-1)-1` / `-2^(bits-1)`，不硬编码）；`:381-382` 把
  `SyncFidelityMetrics.clipped` 拆为 `tx_clipped`/`rx_clipped` + `tx_clip_count`/
  `rx_clip_count` + `tx/rx_positive_rail`/`tx/rx_negative_rail`；削顶判据用
  `v >= positive_rail || v <= negative_rail`（int16 比较，避免 `abs(INT_MIN)` 溢出）。
- `board_package/iq_rf_loopback.hpp:56-57` 新增 `kRfTxClipped="RF_TX_CLIPPED"` /
  `kRfRxClipped="RF_RX_CLIPPED"`；`:135-147` `rf_fidelity_verdict` 先判 `tx_clipped → RF_TX_CLIPPED`
  （TX DAC 过驱动），再判 `rx_clipped → RF_RX_CLIPPED`（RX ADC 满轨）；`:154` `RF_PRESERVES_IQ`
  门槛改为 `!tx_clipped && !rx_clipped`。
- `board_package/iq_digital_loopback_runner.hpp` 的逐文件日志行改为 `tx_peak tx_bits
  tx_positive_rail tx_negative_rail tx_clip_count tx_clipped rx_peak rx_bits rx_positive_rail
  rx_negative_rail rx_clip_count rx_clipped capture_too_short`（原单字段 `clipped` 移除）。

### Task B — 首次 TX-off 负对照瞬态（五）

**要求**：`tx_stop → 销毁/停止 cyclic TX → 确认 TX 已停 → recreate_rx_buffer → ≥1 discard refill
（不计入）→ 采集 3 个独立噪声窗口，RMS 中位数 → 各窗口连续性 → 3 窗口异常不同则返回
`RF_NEGATIVE_CONTROL_UNSTABLE` → 输出 `IQ_RF_LOOPBACK_NEGATIVE_CONTROL_DISCARD` / `_SAMPLE idx=` /
`_SUMMARY noise_rms_median/min/max/noise_stable/tx_stopped_readback`。

**实现**：
- `sdr_adapter/pluto_device.hpp:254-258` 新增纯虚 `virtual bool tx_running() const = 0`；Fake 设备
  `:587-598` 增加 `rf_first_refill_stale`（首次 refill 返回陈旧 TX 回波，模拟刚停 TX 的 DMA 尾）与
  `rf_noise_unstable`（连续 TX-off refill 返回 1×/5×/0.1× 截然不同的 RMS）测试钩子；`:794-801` 声明。
- `sdr_adapter/pluto_device_libiio.cpp:623-626` 实现 `tx_running()`：`txbuf_ != nullptr`（
  `tx_start_cyclic` 创建 / `tx_stop` 销毁 cyclic TX 缓冲）。
- `board_package/iq_rf_loopback_transfer.hpp:51` 新增 `kRfNoiseStableMaxSpread = 0.5`（3 窗口 RMS
  相对展宽上限）；`:62-75` `RfNegativeControl` 拆为 `noise_discard`（陈旧 DMA drain refill，不计入）+
  `noise_window_rms[3]` + `noise_window_cont[3]` + `noise_rms_median/min/max` + `noise_stable` +
  `tx_stopped_readback` + `noise_capture_ok`；`:123-176` 先 `r.tx_stopped_readback = !dev.tx_running()`，
  再 discard refill（`kRfDiscardComplex` 读一次丢弃，记录 `measure_refill`），再采集 3 独立窗口；若
  `(max-min)/max > kRfNoiseStableMaxSpread` → `noise_stable=false`，runner 侧 fail-closed。
- `board_package/iq_rf_loopback_report.hpp:45-51` `RfPerFileResult` 新增 3 窗口负对照摘要标量
  （`tx_stopped_readback`/`noise_stable`/`noise_rms_median/min/max`），仅标量无缓冲。

### Task C — RF 安全工作点扫描（六）

**要求**：`--phase=iq-rf-loopback-level-sweep`，固定 `loopback=0`/`--rf-path=direct-cable`/
`tx-atten=-40`/无自动提功率/无天线/50Ω SMA；扫描 TX 冻结 IQ RMS 512/1024/2048/4096/8192 × RX gain
0/10/20/30 × (tone + PRBS + ≥1 调制)；TX-on 前先负对照；削顶即拒绝该点；输出
`IQ_RF_LOOPBACK_LEVEL_SWEEP` / `_LEVEL_SELECTION recommended_raw_complex_rms_counts/
recommended_rx_gain/selection_reason`。

**实现**：
- `board_package/iq_rf_loopback_level_sweep.hpp`：`make_rf_level_waveform`（tone/PRBS/QPSK 确定性，
  RMS 归一）+ `select_rf_level`（`:266`，选最大 clip-free 高保真档 + RX 中位 RMS 最接近目标的增益，全
  clip / 低 corr / 负对照失败 → `ok=false`，绝不编造工作点）+ `sweep_rf_levels`（`:350`，完整网格，
  Fake/真实 Pluto 共用）。
- `board_package/board_gate9_full_chain_rml23.cpp:2709` `run_iq_rf_loopback_level_sweep`：
  `--rf-path=direct-cable` 强制（`:2728`），`--tx-atten` 必须 ≤ -40 dB（`:2734`，fail-closed），
  2.56 MSPS 冻结采样率强制（`:2790`，abs(actual-2560000) ≤ 5 Hz）；打印 `IQ_RF_LOOPBACK_LEVEL_SWEEP`
  （每点）+ `IQ_RF_LOOPBACK_LEVEL_SELECTION`（推荐点）；`loopback_capability=RF_PATH_NOT_PROVEN`
  恒不变（`:2845`）。
- `board_package/gate9_phase.hpp` 新增 `iq-rf-loopback-level-sweep`；`board_gate9_full_chain_rml23.cpp:3224`
  分发。

### Task D — Route D 冻结工件审计（七）

**要求**：`scripts/audit_route_d_artifacts.py` 校验 Route D 冻结目录（
`/root/rml23_route_d_scale128_*`）：manifest 列、6 文件存在、无 dangling symlink、正确尺寸/SHA、
recovered tensor 精确 8192 字节、quantized size == complex count；输出
`ROUTE_D_ARTIFACT_AUDIT result=PASS|FAIL missing/dangling/size_mismatch/sha_mismatch`。

**实现**：纯 stdlib、`-I` 隔离。`audit(out_dir)`（`:109`）按 `EXPECTED_HEADER`（13 列）校验
manifest 结构与 index 连续性/class_index 范围/hdf5_label==class_index；`COLUMN_SIZE` 精确校验
original=8192 / interp=430080（(1024+2·832)·20·8）/ quant=215040（= interp 之半）/ recovered=8192 /
raw24_a/d=96；`quant_bytes/4 == interp_bytes/8`（quantized complex 数 == interpolated complex 数）；
`sha256_file` 比对 manifest `original_sha256` 列；`find_dangling_symlinks`（`:99`）以
`followlinks=False` 遍历整树。`format_verdict`（`:240`）输出机器可解析单行。

### Task E — Route D2 非训练 4ASK 诚实结论（八）

**要求**：真正实现非训练 4ASK Route D2，用与 Route A 相同的原始 RadioML 冻结样本（240/240），
D0/D1/D2/D3 消融；全局 K 仅由无标签重构误差/量化利用率/削顶率在固定校准子集选择、独立 holdout 固定；
`ROUTE_D2_4ASK_NON_RETRAINING_FIX_PROVEN` 仅当 holdout 4ASK 明显救回 ∧ 其余 3 类不退化，否则
`NON_RETRAINING_4ASK_FIX_NOT_PROVEN`。

**实现**：`scripts/analyze_route_d2_4ask.py` 新增 `compute_verdict(per_class, fourask="4ASK",
improve_frac=0.10, regress_frac=0.10)`（`:377`）：PROVEN iff 4ASK D2 nmse < D0 nmse·(1-0.10) ∧
corr≥D0 corr ∧ clip==0 ∧ 其余每类 D2 nmse ≤ D0 nmse·(1+0.10) ∧ corr≥D0 corr−0.01 ∧ clip==0，否则
NOT_PROVEN；新增 `recovered_tensor_1024`（`:429`，最优延迟对齐提取 [2,1024] fp32）与
`write_d2_artifacts`（`:441`，写 `recovered_tensor_d2_%06d.f32` 8192 字节 + SHA 一致
`d2_recovered_manifest.tsv`）；`--calib-count`/`--holdout-count` 默认 240/240。合成端到端诚实返回
`NON_RETRAINING_4ASK_FIX_NOT_PROVEN`（仅 ~6% 改进 < 10% 阈值），PROVEN 分支由纯单元 self-test 覆盖。

### Task F — D-vs-D2 A/B 门禁（九）

**要求**：Route F 的 D vs D2 A/B 只在全部六门满足后才运行（Route D 审计 PASS + D2 审计 PASS + RF
安全工作点已选 + `RF_PRESERVES_IQ` + 无削顶 + 负对照稳定）；同物理连接/衰减/增益/全局校准，D 与 D2
交织，无 oracle 增益，逐类小样本后全量 240。

**实现**：
- `board_package/iq_rf_loopback_ab.hpp`：`RouteFAbGateInput`（六 bool，默认 false fail-closed）、
  `route_f_ab_gate`（`:57`，严格顺序求值，返回首个失败 reason + 逗号分隔 missing 全集）、
  `route_f_ab_gate_lines`（`:91`，逐门可解析行）。纯头文件、无设备、无 NPU，host 完全可测。
- `board_package/board_gate9_full_chain_rml23.cpp:2871` `run_iq_rf_loopback_ab`：六 bool 由 CLI
  `--route-d-audit-pass=1`/`--route-d2-audit-pass=1`/`--rf-safe-point-selected=1`/
  `--rf-preserves-iq=1`/`--no-clip=1`/`--negative-control-stable=1` 提供（默认 0）；打印
  `ROUTE_F_AB_GATE_LINE`×6 + `ROUTE_F_AB_GATE ok= reason= missing=`；任一门不过 → `gate=BLOCKED`
  emit fail 返回 1，**不打开设备、不建 TX 缓冲、不发射、不分类**；全过 → `gate=PASS` 授权 A/B 采集
  可继续，`loopback_capability=RF_PATH_NOT_PROVEN` 恒不变。
- `board_package/gate9_phase.hpp` 新增 `iq-rf-loopback-ab`；`board_gate9_full_chain_rml23.cpp:3227`
  分发。

---

## §3 文件差异（相对 fix7 `20d843c2…` 基线）

**14 改**：
| 文件 | 变更 |
|---|---|
| `board_package/iq_digital_loopback_sync.hpp` | `SyncFidelityMetrics.clipped` → tx/rx_clipped + rails + clip_count |
| `board_package/iq_digital_loopback_runner.hpp` | 逐文件日志行 tx/rx 削顶字段拆分 |
| `board_package/iq_rf_loopback.hpp` | `RF_TX_CLIPPED`/`RF_RX_CLIPPED` token + 噪声 rails + 保真门槛 |
| `board_package/iq_rf_loopback_report.hpp` | 3 窗口负对照摘要标量 |
| `board_package/iq_rf_loopback_runner.hpp` | Task A 指标 + Task B 瞬态（3 窗口 + 稳定性 fail-closed） |
| `board_package/iq_rf_loopback_transfer.hpp` | discard refill + 3 独立噪声窗口 |
| `sdr_adapter/pluto_device.hpp` | `tx_running()` 纯虚 + RF 回波测试钩子 |
| `sdr_adapter/pluto_device_libiio.cpp` | `tx_running()` 实现 |
| `board_package/board_gate9_full_chain_rml23.cpp` | sweep + ab 两 phase 包装/分发 |
| `board_package/gate9_phase.hpp` | 新增 `iq-rf-loopback-level-sweep` / `iq-rf-loopback-ab` |
| `host_tests/test_iq_rf_loopback.cpp` | Task A/B 测试更新（TX/RX 削顶 + 负对照瞬态） |
| `scripts/analyze_route_d2_4ask.py` | `compute_verdict` + `write_d2_artifacts` + 240/240 默认 |
| `host_tests/build_host_tests.sh` | 构建 sweep + ab 测试 |
| `host_tests/run_tests.sh` | 运行 sweep + ab 测试 |

**7 新**：
| 文件 | 内容 |
|---|---|
| `board_package/iq_rf_loopback_level_sweep.hpp` | RF 安全工作点扫描（波形/选点/全网格） |
| `host_tests/test_iq_rf_loopback_level_sweep.cpp` | host sweep 测试 |
| `scripts/audit_route_d_artifacts.py` | Route D 冻结工件审计 |
| `board_package/iq_rf_loopback_ab.hpp` | 纯六门禁（D-vs-D2 A/B 前置） |
| `host_tests/test_iq_rf_loopback_ab.cpp` | host 门禁测试 |
| `scripts/package_iq_rf_loopback_fix8.py` | 打包器（dependency closure fail-closed） |
| `docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX8_AUDIT.md` | 本审计 |

**红线合规**：无模型/标签/NPU 二进制/RTL/XDC/位流/Flash 改动；不重训/不微调；不新增 4ASK 专用分类规则；
不按标签选 RF 工作点；不逐文件用参考答案校正分类；不放宽 corr/SNR/residual/RSS 阈值；不自动提高 TX
功率；TX 衰减保持 -40 dB；不覆盖 fix7 及更早历史工件；API 未连接/未操作板卡；host 测试不能升级
`RF_PATH_PROVEN`。

---

## §4 核心代码位置

- 削顶 rails + 拆分：`iq_digital_loopback_sync.hpp:320-325, 381-388`；`iq_rf_loopback.hpp:56-57,
  135-154`；`iq_digital_loopback_runner.hpp:543-570`
- 负对照瞬态：`pluto_device.hpp:254-258, 587-598, 794-801`；`pluto_device_libiio.cpp:623-626`；
  `iq_rf_loopback_transfer.hpp:51, 62-75, 123-176`；`iq_rf_loopback_report.hpp:45-51`
- RF 安全工作点：`iq_rf_loopback_level_sweep.hpp:266, 328, 339, 350`；
  `board_gate9_full_chain_rml23.cpp:2709-2855`
- Route D 审计：`scripts/audit_route_d_artifacts.py:99, 109, 240, 297`
- Route D2 结论：`scripts/analyze_route_d2_4ask.py:377, 429, 441`
- A/B 门禁：`iq_rf_loopback_ab.hpp:41, 57, 91`；`board_gate9_full_chain_rml23.cpp:2871-2923`
- phase 分发：`board_gate9_full_chain_rml23.cpp:3196, 3224-3228`

---

## §5 离线验证（本轮，不碰板）

1. `host_tests/build_host_tests.sh` 全绿（含新增 `test_iq_rf_loopback_level_sweep` 链接
   `../sdr_adapter/pluto_tx.cpp`、`test_iq_rf_loopback_ab` 纯头）；
2. `host_tests/run_tests.sh` → **`ALL HOST TESTS PASSED`**；
3. fix8 三套 RF 测试：`test_iq_rf_loopback` 75/0、`test_iq_rf_loopback_level_sweep` 40/0、
   `test_iq_rf_loopback_ab` 28/0；
4. `host_tests/syntax_check.sh` → `gate7/gate9/gate10/gate9_rml23: syntax OK`；
5. `scripts/audit_route_d_artifacts.py --self-test` 5/5 correct（1 项 Windows 符号链接特权跳过，属宿主
   限制非审计器缺陷）；
6. `scripts/analyze_route_d2_4ask.py --self-test` 10/10 correct（含 PROVEN / 回归 NOT_PROVEN / D2 工件
   生成分支）；
7. 打包器 `audit_dependency_closure` OK（所有改动头已列入 `ROUTE_F_FIX8_FILES`）；两份 tarball 确定性
   重打包一致；独立解包 `sha256sum -c` 全 OK。

---

## §6 官方文档引用（Task 11）

- **libiio 官方文档**：`iio_channel_convert()`（硬件格式→主机格式采样转换，对应 host 镜像的
  `format_convert_raw_to_host` 语义，`iio_channel_convert_inverse()` 为反向）——
  <https://analogdevicesinc.github.io/libiio/>，API 参考
  <https://analogdevicesinc.github.io/libiio/main/api/c/debug/>。
- **AD9361/AD9363/AD9364 Linux IIO 收发器驱动**（`in_voltage_sampling_frequency` /
  `out_voltage_sampling_frequency`、`rx_path_rates`/`tx_path_rates`、增益/衰减属性，本板 AD9364 即走
  此驱动）—— <https://wiki.analog.com/resources/tools-software/linux-drivers/iio-transceiver/ad9361>
  （镜像 <https://developer.analog.com/docs/linux/latest/drivers/iio-transceiver/ad9361.html>）。
- **AD9364 数据手册 / 参考手册**（UG-673 数据手册 + UG-672 寄存器映射；AD9363 为 UG-1040/UG-1057；
  三者引脚兼容）—— <https://www.analog.com/en/products/ad9364.html> 及
  <https://www.analog.com/en/products/ad9363.html>。
- **ADALM-PLUTO**（Rev.C 板载 AD9364，1T1R）—— <https://wiki.analog.com/university/tools/pluto>。

---

## §7 板端复测（用户执行；本审计不写死 ip、不强制）

```
第一步（Route D / D2 工件审计，先建立六门禁的前两门）：
python3 -I scripts/audit_route_d_artifacts.py --out-dir /root/rml23_route_d_scale128_* \
  --json /root/rml23_route_d_audit_fix8.json
python3 -I scripts/analyze_route_d2_4ask.py --out-dir /root/rml23_route_d2_* \
  --d2-out-dir /root/rml23_route_d2_fix8_out --json /root/rml23_route_d2_fix8.json

第二步（RF 安全工作点扫描，判责后按推荐点重跑）：
./scripts/run_gate9_rml23.sh --phase=iq-rf-loopback-level-sweep --center=2400000000 \
  --tx-atten=-40 --rf-path=direct-cable > /root/rml23_route_f_fix8_sweep.log 2>&1
  预期观测：IQ_RF_LOOPBACK_LEVEL_SWEEP（每点 corr/clip/negative_control_ok）+
  IQ_RF_LOOPBACK_LEVEL_SELECTION ok=1 recommended_raw_complex_rms_counts=… recommended_rx_gain=…
  sweep result=PASS 只表判责成功，非回环保真 PASS。

第三步（物理 RF 回环，确认 RF_PRESERVES_IQ + 无削顶 + 负对照稳定）：
./scripts/run_gate9_rml23.sh --phase=iq-rf-loopback --center=2400000000 --rx-gain=10 \
  --tx-atten=-40 --rf-path=direct-cable --rf-calib-count=8 --input-kind=generated-2p56m \
  --frozen-dir=DIR > /root/rml23_route_f_fix8_rf.log 2>&1
  预期观测：NEGATIVE_CONTROL_SUMMARY noise_stable=1 tx_stopped_readback=1、每文件 fidelity token、
  RF_PRESERVES_IQ 仅由板端运行建立，host 测试永不升级 RF_PATH_PROVEN。

第四步（六门全过才允许 D-vs-D2 A/B 门禁授权）：
./scripts/run_gate9_rml23.sh --phase=iq-rf-loopback-ab --route-d-audit-pass=1 \
  --route-d2-audit-pass=1 --rf-safe-point-selected=1 --rf-preserves-iq=1 --no-clip=1 \
  --negative-control-stable=1
  预期观测：ROUTE_F_AB_GATE_LINE ×6 全 ok=1 + ROUTE_F_AB_GATE ok=1 reason= missing=；任一门为 0 则
  gate=BLOCKED 且绝不发射。D-vs-D2 交织采集本身是板端活动，复用 fix7 iq-rf-loopback runner。
```

---

## §8 交付

2 工件（独立补丁 + 合并全量），SHA256SUMS manifest + 独立解包 `sha256sum -c` 校验，精确
路径/字节/文件数/manifest 行数/64-hex SHA 见 `dist/RML23_IQ_RF_LOOPBACK_FIX8_DELIVERY.txt`。
历史包（fix7 `20d843c2…` 及更早全部）原样保留。
