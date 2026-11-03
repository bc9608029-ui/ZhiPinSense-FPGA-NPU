# M29 RML23 Stage G — RadioML/合成IQ 无射频四路数字注入判责（A/B/C 三路 + D 路 round-trip）

状态：`M29-RML23-SYNTHETIC-IQ-INJECTION-READY-FOR-BOARD-TEST`（最高允许，未上板复测）

冻结身份不变：model json `d43a2284…` / raw `2425d990…` / params_md5 `7966a482…` / 位流 `22fec95c…`。
本阶段**只新增** `--phase=synthetic-iq`，**不修改**模型/标签/golden/live-rx 语义/RTL/位流/Flash，**不打开任何 IIO/SDR 设备**，**不启动 TX**。

---

## 0. 目的与判责逻辑

Stage G 在**不依赖射频硬件**的前提下，把「真实域 QPSK→QAM 跳变」的判责从「外部射频实测」前移为
**四路数字注入**，分别隔离模型在不同输入边界下的混淆：

| 路 | `--source` | `--inject-point` | 输入来源 | 隔离的变量 |
|---|---|---|---|---|
| A | `radioml` | `model-input` | 冻结 test split 的真实 RadioML2018.01A 帧（HDF5 → .bin + manifest） | **模型固有混淆**（干净真实域样本直接进 NPU，无任何板端预处理） |
| B | `generated` | `model-input` | 128 kSPS（8 sps）RRC 成形 BPSK/QPSK/4ASK/16QAM，直接切窗进 NPU | **合成干净信号**下模型的调制混淆（控制合成器本身正确） |
| C | `generated` | `raw-rx` | 2.56 MSPS（160 sps）int16 → 走**真实生产 `PreprocessChain`**（÷2048→NCO off→2.56M→128k 多相 FIR→×rec_scale）→ NPU | **板端预处理链**是否会引入/改变混淆；并以 replay 验证 C 的最终 tensor 与 model-input 路径逐位一致 |
| D | `radioml` | `raw-rx-reconstructed` | 与 A **同一**冻结 test 帧 → 组合 complex → 确定性 ×20 多相 FIR 插值至 2.56 MSPS → 显式统一幅度映射 → int16 → **真实生产 `PreprocessChain`** → 恢复 `[2,1024]` → NPU | **生产接收预处理往返**是否保持真实 RadioML 样本的类别与 logits（A 与 D 一一对应判责） |

A/B/C 均报 **测量值**（模型的真实混淆），**不设准确率 PASS 阈值**。gate 只判定「注入机制健全」：
每一帧都被注入且合法、route C 的最终 tensor 通过 model-input 推理路径逐位重放一致（NPU 确定性 +
边界同一性）、NPU bring-up/reset 纪律成立。route D 另有自身的逐帧 A-vs-D 判责（见 §3.4 五条归因规则），
同样是测量值，不设准确率 PASS 阈值。

---

## 1. 红线（全部遵守）

- 禁碰板、禁训练、禁写任何 `*_PASS`（`NPU_PASS / RML23_LIVE_HARDWARE_PASS / UI_HARDWARE_PASS / UI_VISUAL_PASS / RF_PASS / HARDWARE_PASS / PROJECT_COMPLETE / FINAL_*`）。
- A 路必须用**冻结 test split**（`rml24_split_indices.npz` 的 `test_indices`），**绝不**使用 240 帧 `deployment_golden` 验证子集（红线 7）；不得把 deployment golden 冒充独立测试集。
- 不允许凭假设补造 RadioML 样本：A 路样本全部来自真实 HDF5 冻结 test split，逐帧做 HDF5 源切片字节比对。
- 不打开 IIO/SDR 设备、不启动 TX、不修改模型/标签/golden/live-rx 语义/RTL/位流/Flash。
- 不通过多数表决/强制标签掩盖问题；所有预处理与类别无关（归一化是全局策略，绝不 per-class）。
- RadioML 数据集不存在时 fail-closed 报告 `RADIOML_DATASET_MISSING`（extractor 对缺失 HDF5/npz 直接非零退出）。
- 不根据离线 host 测试提前写「分类修复完成」；本轮最高状态即 `…-READY-FOR-BOARD-TEST`。

---

## 2. 新增文件与职责

| 文件 | 类型 | 职责 |
|---|---|---|
| `board_package/synthetic_iq_generator.hpp` | 新增 | 确定性 RRC 成形调制波形生成器（BPSK/QPSK/4ASK/16QAM，单位功率星座 + 单位符号能量 RRC；`symbol_indices` 共享种子符号流；`pulse_shape` 去瞬态；`apply_normalization` 全局策略；`quantize_int16` 记录真实 RMS/peak/clip）。iCraft/libiio-free，host 可测。 |
| `board_package/synthetic_iq_runner.hpp` | 新增 | 四路 tensor 源 + A 路 manifest 解析 / fail-closed 字节校验。**只产 tensor、不碰设备、不跑 NPU**；板端 runner 把它与 `chain::NpuClassifier24` 组合。 |
| `board_package/synthetic_iq_roundtrip.hpp` | 新增（D 路） | 确定性 ×20 多相 FIR 插值器（Blackman-Harris-4 windowed-sinc，N=640，32 taps/相，DC 增益归一 20，群延迟 319.5 输出样点，Type-II 偶对称）+ 显式统一幅度映射（信号 RMS 不被 guard 稀释）+ 复用真实 `chain::PreprocessChain` 的完整往返；A-vs-D 时间对齐 / LS 复增益相位 / NMSE / EVM / 相关 / RMS·DC·PAPR / I·Q 交换·共轭（仅诊断）度量；edge_policy（zero|reflect）+ 有效中心区间。iCraft/libiio-free。 |
| `board_package/gate9_phase.hpp` | 修改 | `valid_phase()` 增 `"synthetic-iq"`。 |
| `board_package/board_gate9_full_chain_rml23.cpp` | 修改 | 新增 `run_synthetic_iq_phase(...)` + dispatch + `run_route_d_roundtrip(...)`（D 路往返、A/D 双推理、replay、逐帧判责、artifact 保存、D 混淆矩阵 + 按 SNR 统计）；错误信息补 `synthetic-iq`。 |
| `scripts/extract_radioml_stage_g.py` | 新增 | A 路前置：冻结 test split → `[2,1024]` fp32 .bin + `manifest_a.tsv/json`；逐帧 HDF5 源切片字节比对；记录 HDF5/npz 全量 SHA。（D 路复用同一抽取目录。） |
| `scripts/verify_radioml_stage_g.py` | 新增 | A 路独立字节一致性校验器（与 extractor 独立实现，重新从 HDF5 读源切片比对 + SHA + label/SNR 交叉）。 |
| `scripts/analyze_roundtrip_stage_g.py` | 新增（D 路） | host 独立重推导 D 路逐帧 A-vs-D 表 + PSD/90/95/99% OBW + 归因汇总 + D 混淆矩阵 + 按 SNR 统计 + 全 artifact SHA（与板端 roundtrip_manifest.tsv 交叉）。 |
| `host_tests/test_synthetic_iq_generator.cpp` | 新增 | 生成器 47 断言（星座单位功率、RRC 单位能量、确定性、归一化策略、量化统计、负例 fail-closed）。 |
| `host_tests/test_synthetic_iq_runner.cpp` | 新增 | runner 39 断言（A 路 ok/fail-closed 全套、B/C 生成确定性、B-vs-C 保真 NMSE<0.005/offset=-585/gain≈0dB）。 |
| `host_tests/test_synthetic_iq_roundtrip.cpp` | 新增（D 路） | 往返 48 断言（FIR 身份/每相 DC≈1/对称、×20 插值确定性、纯延迟增益相位精确恢复、双音+QPSK 往返保真 NMSE<0.001/corr>0.999、edge policy、fail-closed 负例）。 |
| `host_tests/build_host_tests.sh` | 修改 | 增 `test_synthetic_iq_generator` + `test_synthetic_iq_runner` + `test_synthetic_iq_roundtrip` 三个构建目标。 |
| `host_tests/run_tests.sh` | 修改 | 增三个测试的运行入口。 |
| `scripts/run_gate9_rml23.sh` | 修改 | 头注释补 `--phase=synthetic-iq` 四路用法（薄封装，参数经 `"$@"` 透传，功能本已支持）。 |

---

## 3. 四路细节

### 3.1 Route A（真实 RadioML，`model-input`）

- 前置（host，非板端）：`scripts/extract_radioml_stage_g.py --dataset-hdf5 … --split-npz … --classes BPSK,QPSK,4ASK,16QAM --snr-db 20,22,24,26,28,30 --count 500 --out-dir <dir>`。
- 抽取合同：`X[hdf5_idx] (1024,2) → .T (2,1024)` planar（plane0=I / plane1=Q）→ 8192 字节 fp32 LE，**无归一化、无 I/Q 交换、无字节改动**；写后重读与 HDF5 源切片逐字节比对。
- manifest 列（TSV，板端 `split_tsv` 解析）：`index \t source_index \t hdf5_label \t snr_db \t class_index \t class_name \t bin_file \t bin_sha256`；JSON 全量 provenance（含 `hdf5_sha256` / `split_npz_sha256` / 采样算法 / 每帧标签与 SNR）。
- 确定性采样：HDF5 是 SNR-major 排序，故按类 × SNR 均匀分配（每 SNR 升序 HDF5 row id），避免简单升序把所有帧塌到最低 SNR。
- 板端 `--radioml-bin-dir`：`load_route_a` fail-closed（缺 manifest / 行格式错 / index 不连续 / class_index∉0..23 / hdf5_label≠class_index / 危险 bin_file（含 `/`、`\`、`..`）/ bin_sha256 非 64 hex / .bin 缺或非 8192 字节 / SHA 不匹配，任一即抛）。
- 直接把 `.hdf5` 或 `--radioml-hdf5`/`--dataset-hdf5` 传给板端 → `RADIOML_HDF5_HOST_EXTRACTION_REQUIRED`。

### 3.2 Route B（合成，`model-input`）

- 128 kSPS（8 sps）RRC（β=0.35，span 8）稳态波形，切 1024 样本窗 → `[2,1024]` planar fp32。
- `--modulation all|BPSK|QPSK|4ASK|16QAM`（默认 all=4 类）、`--norm none|complex-rms-1`（默认 none）、`--seed`（默认 0x39e5）、`--count`（默认 240/类）。
- 源类索引（冻结 24 类序）：BPSK=3，QPSK=4，4ASK=1，16QAM=12。

### 3.3 Route C（合成，`raw-rx`）

- 2.56 MSPS（160 sps）int16 → `chain::PreprocessChain`（`÷2048` → NCO off → 2.56M→128k 多相 FIR → `×rec_scale=2048/rms_counts`）→ `[2,1024]`。
- `rec_scale = calibrate_rec_scale(16.0, kTargetModelRms) = 128`，使 C 的最终 tensor 落在与 B 相同的 model-domain 尺度（复 RMS≈1.0，增益≈0 dB）。
- 板端对 C 的每个最终 tensor 再走一遍 model-input 推理路径并 `memcmp` 逐位一致（`replay_ok`），证明 NPU 固定输入确定性 + 无隐藏 per-route 变换；`replay_mismatch` 记入 GATE_RESULT。
- 记录 `quant_rms/quant_peak/clip`（真实 int16 量化统计，非仅请求值）。
- `--raw-complex-rms-counts`（默认 16.0）。B/C 共享同一 `(modulation, seed)` 符号索引流 → 符号序列逐位相同，仅上采样倍率不同（8 vs 160 sps）。

### 3.4 Route D（真实 RadioML round-trip，`raw-rx-reconstructed`）

调用链（与 A 路**同一**冻结 test tensor，requirement 1）：

```
RadioML 原始 [2,1024] fp32 @128k
  → 组合 complex → 确定性 guard（zero|reflect，绝不循环拼接/跨样本拼接）
  → 确定性 ×20 多相 FIR 插值至 2.56 MSPS（Blackman-Harris-4 windowed-sinc，N=640）
  → 显式统一幅度映射（信号 RMS→16 counts，guard 不稀释幅度参考）→ 交错 int16
  → 真实生产 chain::PreprocessChain（÷2048→NCO off→2.56M→128k 多相 FIR→×rec_scale）
  → pull_tensor 恢复 [2,1024]（对齐后）→ NPU24 → merge23 → result
```

- **requirement 3**：插值器是确定性 FIR/polyphase（`h[n]=L·sinc((n−c)/L)·BH4`，N=640，32 taps/相），**绝不线性插值**。
- **requirement 4**：每帧先打印 `ROUNDTRIP_INTERPOLATOR up=20 down=1 taps_total=640 taps_per_phase=32 cutoff_hz=64000 fs_out_hz=2560000 group_delay_out=319.5 dc_gain_total=20 window=Blackman-Harris-4 edge_policy=… guard=832 …`。
- **requirement 5**：有限 1024 点用确定性 guard（默认 zero，832；reflect 需 guard<1024）；不静默循环、不把拼接边界送入 NPU；报告**全 1024 与排除边缘中心 [32,992)** 两组误差（`nmse_full` vs `nmse_center`），并记录 `edge_policy` 与中心区间。
- **requirement 6**：逐帧计算 `delay_offset`（整数互相关对齐）、LS 最优单一复增益/相位、`nmse_full/nmse_center/evm_pct/corr`、`rms/dc/papr`、`corr_swap/corr_conj`（I/Q 交换与共轭**仅诊断**，绝不自动选择最优变换）；PSD 与 90/95/99% OBW 由 host `analyze_roundtrip_stage_g.py` 从保存的 artifact 独立重算。
- **requirement 7**：保存 `radioml_original_%06d.f32`、`interpolated_2p56m_%06d.f32`、`quantized_raw_rx_%06d.ci16`、`recovered_tensor_%06d.f32`、`raw24_a_%06d.f32`、`raw24_d_%06d.f32` + `roundtrip_manifest.tsv`（记录 original SHA）；host 分析器重算全部 artifact SHA 并交叉。
- **requirement 8**：逐帧比较 A raw24 top1 vs D raw24 top1、24 维 logits `max_abs/mean_abs/cosine`、merged23 类别是否一致、正确标签是否保持。
- **requirement 9**：D 路独立混淆矩阵（`ROUNDTRIP_D_CONFUSION`）+ 按 SNR 统计（`ROUNDTRIP_SNR`）。
- **requirement 10**：同一 recovered tensor 再次走 model-input 入口推理，raw24 必须逐位一致（`replay_ok`），`replay_mismatch` 记入 GATE_RESULT。

**五条归因规则（逐帧，测量值，绝不判「分类修复完成」）：**

| 条件 | 归因 |
|---|---|
| A 正确 且 D 正确 且 logits cosine ≥ 0.999 | `PREPROCESS_PRESERVES_RADIOML_DOMAIN` |
| A 正确、D 错误 且恢复 tensor 显著失真（`nmse_center` > 0.01） | `PREPROCESS_ROUNDTRIP_MISMATCH` |
| A 与 D 都错误 | `MODEL_FAILS_ON_RADIOML_HELDOUT`（不得归罪预处理） |
| A 正确、恢复 tensor 数值接近（`nmse_center` ≤ 0.01）但 D 翻转 | `MODEL_INPUT_SENSITIVITY`（报告 margin 与 logits 变化） |
| 有限窗口边缘导致无法公平比较（`nmse_center` > 0.1） | `RADIOML_ROUNDTRIP_EDGE_INCONCLUSIVE` |

补充两档（不在五条内，如实记录）：A 正确+D 正确但 cosine<0.999 → `PRESERVED_LABEL_BUT_LOGITS_SHIFTED`；
A 错误+D 正确 → `D_IMPROVED_OVER_A`。

Route D 的 GATE_RESULT 只判定**机制健全**：`(processed>0) && (replay_mismatch==0) && (artifacts_failed==0) && npu_discipline`。
逐帧打印 `ROUNDTRIP frame=… … raw24_a_top1=… raw24_d_top1=… merged_a_top1=… merged_d_top1=… label=… a_correct=… d_correct=… logits_max_abs=… logits_mean_abs=… logits_cosine=… merged_consistent=… replay_ok=… attribution=…`；报告必须提供 A 与 D 一一对应的逐帧表（**不给总体准确率**）。

---

## 4. GATE_RESULT 语义（测量，非准确率）

```
GATE_RESULT=PASS ⇔ (processed>0) && (valid==processed) && (replay_mismatch==0) && npu_discipline
detail 恒含  measurement=model_confusion_no_accuracy_threshold
```

逐帧打印 `SYNTHETIC_IQ route=X frame=… src=… src_class=… snr_db=… raw24_top1=… merged23_top1=… label=… margin=… raw24_match=… merged23_match=… [replay_ok=1|0]`，
末尾按源类打印 `SYNTHETIC_IQ_CONFUSION src_class=… total=… correct23=… pred23_*=…`。**这些是测量值，不进入 PASS 判定**。

---

## 5. 离线验证（本轮已执行，不碰板）

1. `host_tests/test_synthetic_iq_generator` — **47/47 PASS**（生成器确定性、单位功率/能量、归一化、量化统计、fail-closed 负例）。
2. `host_tests/test_synthetic_iq_runner` — **39/39 PASS**（A 路 ok + 全套 fail-closed、B/C 确定性、**B-vs-C 保真：align_nmse<0.005、offset==-585、gain≈0 dB**）。
3. `host_tests/test_synthetic_iq_roundtrip` — **48/48 PASS**（D 路：FIR 身份/每相 DC≈1(7e-7)/对称、×20 插值确定性、纯延迟增益相位精确恢复、双音+QPSK 往返 NMSE<0.001/corr>0.999/gain≈0dB/无 clip、edge policy、fail-closed 负例）。
4. `scripts/analyze_roundtrip_stage_g.py --self-test` — **2/2 PASS**（OBW wrap 修正、AM-SSB merge 语义）。
5. 全量 host 测试 `run_tests.sh` — **ALL HOST TESTS PASSED**（含 `test_board_build.sh`、`test_rml23_build.sh`、`test_cli_override.sh`）。
6. `bash -n` syntax check gate9 全绿；`python -m py_compile` 打包/分析脚本全绿。
7. 打包解包 `sha256sum -c` 全 OK（见交付说明）。

host 自洽全绿 **不等于** 板端判定；真实混淆率只能在板端由用户跑
`run_gate9_rml23.sh --phase=synthetic-iq --source=… --inject-point=…` 观测（我禁碰板）。

---

## 6. 已知限制（如实记录）

- A/D 路的真实域结论仅对 `--classes BPSK,QPSK,4ASK,16QAM` 与所选 SNR 成立；不同类/SNR 需重跑 extractor。
- A/D 路抽取依赖 host 侧 21.4 GiB HDF5（`e3dd0bef…`）与冻结 split npz；二者任一缺失即 fail-closed。
- D 路边缘：guard 区域引入插值/抽取瞬态，中心 [32,992) 与全 1024 两组误差同时报告；`edge_policy=reflect` 要求 guard<1024（否则 fail-closed）。
- D 路插值器 FIR 是窗口化 sinc（截止 64 kHz，即输入 Nyquist）；不同插值倍数/截止不可参数化（板端锁定 20×，避免近似实现）。
- 本轮只做**注入判责仪表**，不训练、不改模型、不判「分类修复完成」；若三路均复现 QPSK→QAM 跳变，则判责进一步收敛为模型域泛化（与 Stage C/D/E 结论一致）。D 路若 `MODEL_FAILS_ON_RADIOML_HELDOUT`，则 A 与 D 同错、不得归罪预处理。
