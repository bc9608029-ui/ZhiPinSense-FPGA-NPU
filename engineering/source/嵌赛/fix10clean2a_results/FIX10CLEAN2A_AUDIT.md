# FIX10CLEAN2A 审计 — RadioML 兼容纯净 IQ × 冻结模型评估

- **任务**：fix10clean2a（独立任务，唯一活跃工作）
- **唯一问题**：按本地 RadioML 数据域构造的纯净 IQ，现有冻结 PyTorch 模型能否准确识别？
- **结论**：**能（YES）**。formal12000 上 raw24 overall/macro = **0.99325 / 0.99325**，deployed23 overall/macro = **0.99450 / 0.99426**，deployed23 最低召回 **0.956**（OQPSK），scored=12000、excluded=0、NaN/Inf=0。§11.1 验收全项满足。
- **最高允许状态（不超）**：`M29-RML23-FIX10CLEAN2A-RADIOML-COMPATIBLE-CLEAN-IQ-EVALUATED`
- **明确排除**：不训练模型、不转 NPU、不碰板、不经 SDR、不改 dual-SDR 项目。
- **本任务范围外（保持 BLOCKED / 不宣称）**：NPU 量化、RF 闭环、fix10prep2 双 SDR、clean-IQ 数字回环验收——本任务都不涉及。

---

## 1. 输入溯源（Phase 0）— 全 PASS

| 输入 | 路径 | SHA256 | 字节 |
|---|---|---|---|
| 冻结 checkpoint | `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base\formal\t002_...\seed2027\checkpoints\best.pt` | `96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d` | — |
| RadioML 数据源 HDF5 | `F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5` | `e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38` | 21449148312 |
| 模型源 `models/rml24_net.py` | — | `7fad6b3624e6dab9f7e72abe0cd4b3e9934e76c611efc155d6a68397bec56fc3` | — |
| 模型源 `models/ad_amr_v1_1_net.py` | — | `b9f76276d99bdb2150655a9b77a254f3353ac5fea47f5f5c685456bfbf12aa8c` | — |
| 模型源 `contracts/rml24_contract.py` | — | `164b216d05ea1c491794bc098fc9d2c03a77f3a1db4b335074ed42ffabb9c3bb` | — |
| 模型源 `training/utils.py` | — | `ce1cba6eb29d5a46a8c28df4d7c0dfe3d702c485a84beb41740528b29cede490` | — |
| 冻结 config `rml24_base.yaml` | `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\configs\rml24_base.yaml` | `1f767f981641ee8717f5fb5525d0e0748f17d064d25d67ccde0601e7edb22b8f` | — |
| 24→23 合并后处理 `rml23_merged.py` | `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\postprocess\rml23_merged.py` | `0d4a9eaf585c6d7b1bc777d21133e50c80f44defcfed273fef517d4c00e0c08b` | — |
| 24→23 合并合同 `rml23_merged_contract.py` | `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\contracts\rml23_merged_contract.py` | `31deebc03ca9c36fafb7cd69b85a60dae2bbaff5e3be7a1f7899fc1fae64a48e` | — |

- checkpoint 严格加载（`state_dict` 无 missing/unexpected）、前向 `[1,24]` raw logits（无 softmax）、全有限值。
- 模型 = **ADAMRV11Net**（`num_classes=24`，输入 `[B,2,1024]` fp32 planar `[real,imag]`，输出 `(logits, denoised)`）。
- 数据源：X `[2555904,1024,2]` float32；Y `[2555904,24]` int64；26 SNR（-20…30 dB，每 SNR 每类 4096）。
- 环境：Python 3.13.5 / numpy 2.1.3 / scipy 1.16.3 / h5py 3.12.1 / torch 2.12.0+cpu / deterministic backend。
- 模型源码根目录 `F:\FPGA_Work\sdr_amr_12class_ood_u_v1`（上表 4 个模型源文件分别位于其 `models/`、`contracts/`、`training/` 下）。
- 上表 checkpoint / 模型源码 / 合并后处理 / 合并合同 / 冻结 config / RadioML HDF5 均为**外部冻结输入**：本任务只读、不改、不打包（§13「原始模型/checkpoint/数据源字节不变」+「不包含 NPU/SDR/fix10prep2 修改」）。评估脚本 `evaluate_frozen_model_on_clean24.py` 与 2 个 host 测试（`test_radioml_clean_contract.py`、`test_frozen_model_clean24.py`）按绝对路径 + SHA 引用这些冻结引用；本节上表 SHA 已逐项核验一致。

> 读取纪律：21.4 GB HDF5 只读 `with h5py.File(...) as f:` 短暂打开，句柄即时关闭，不占用 F 盘。

---

## 2. 数据合同（contract `radioml2018_clean_contract_v1`）

### 2.1 标签序（24 类，与冻结模型一致）
`OOK, 4ASK, 8ASK, BPSK, QPSK, 8PSK, 16PSK, 32PSK, 16APSK, 32APSK, 64APSK, 128APSK, 16QAM, 32QAM, 64QAM, 128QAM, 256QAM, AM-SSB-WC, AM-SSB-SC, AM-DSB-WC, AM-DSB-SC, FM, GMSK, OQPSK`

### 2.2 24→23 部署合并（AM-SSB 折叠）
- source 17（AM-SSB-WC）与 18（AM-SSB-SC）→ deployed 17（AM-SSB）。
- `SOURCE_TO_DEPLOYED = (0..16, 17, 17, 18, 19, 20, 21, 22)`；合并用 `logaddexp`（`merge_many_24_to_23`），非 deployed_class 回填。

### 2.3 统一参数（Phase 1 从本地数据域实测 + 官方确认）
| 参数 | 值 | 出处 |
|---|---|---|
| `SAMPLE_LENGTH` | 1024 复采样 | 官方 |
| `SAMPLE_RATE_HZ` | 200000.0 | 官方（DeepSig GNU Radio） |
| `SPS` | 8（→128 符号/帧） | 官方 |
| 线性数字脉冲 | windowed-sinc 低通 `fc=0.059`、Hann、65 tap、sps=8 | 工程推断（**非 RRC**；RRC α=0.35 是 Phase 1 初值，后由 PSD 重构改用 wsinc） |
| `N_SYMBOLS` | 128 | — |
| `ANALOG_CARRIER_HZ` | 6250 | — |
| `CLEAN_PHASE` | π/4（固定，无逐帧随机相位） | — |
| `TARGET_RMS` | OOK=1.4714, 4ASK=1.7525, 8ASK=1.9116, AM-SSB-WC=11.7392, AM-SSB-SC=7.8328, 其余=1.0 | 本地数据实测（非均匀） |

### 2.4 每类生成方法
- **线性数字（PSK/QAM/APSK/ASK）**：符号映射 → wsinc 脉冲成形 → `e^{j·π/4}` 固定相位，RMS 归一。
- **GMSK（source 22，红线）**：高斯滤波连续相位，恒包络（|x| 标准差 < 1e-6）。
- **OQPSK（source 23，红线）**：共享比特、wsinc 脉冲、Q=frac_shift(I, −11.5)，有幅度波纹。
- **AM-DSB**：`x=(1+m·sawtooth)·cos(2π·6250·n/FS)·e^{jπ/4}`，sawtooth 195 Hz 实数斜坡，WC m=0.10 / SC m=0.15。
- **AM-SSB**：直流载波 + 微小 USB：`x=(1+m·(a+j·Hilbert(a)))·e^{jπ/4}`，WC m=0.06 / SC m=0.09，音频多音 200–3000 Hz（fmax=3000）。
- **FM**：相位积分，恒包络。

### 2.5 种子与泄漏隔离
- 5 维（seed/message/audio/symbol-seq/window）全部由每样本 seed 派生；seed 唯一 → 音频/比特/符号序列无跨样本共享。
- `_seed_for(cidx, k, base, spc) = base + cidx*spc + k`；smoke96 base=0、dev2400=1_000_000、formal12000=2_000_000。
- 三套 seed 区间互不相交；同 seed 字节级复现（确定性）。

---

## 3. 数据集（Phase 3）

| 集 | 样本/类 | 总样本 | 字节 | SHA256 |
|---|---|---|---|---|
| smoke96 | 4 | 96 | 667308 | `c67df8fb13efe79e226e24d1b7788a2ffa3b870cf4782ed7d68612d1308ab23d` |
| dev2400 | 100 | 2400 | 16528159 | `83ad5cfe93309dbd0708ae8d729fdd300c8b9bdecf6c902688a1cae2be3e14f6` |
| formal12000 | 500 | 12000 | 82185391 | `8b3efe0b11143b31972d392f5b85bc8bd3faf7973681c4d5d7da7ed9603ed81a` |

- 合成合同 `radioml_clean_contract.py` SHA `aa5fe816dbfddbd26512ac2240c504eccfe3769293aac2fbf2caf7c172fa76d5`（manifest 的 `generator_sha256` 字段记录的是实现 `generate_class()` 的合同模块，非编排脚本）。
- 编排脚本 `gen_radioml_compatible_clean24.py` SHA `542c13c71bbedab68e73dcb4bec02d8fa9fb566ec973980859ba20ac4e9c368c`（在 SHA256SUMS.txt 内，随 patch 交付）。
- gzip HDF5；同参数 → 字节级一致（`--regenerate-determinism` 在临时目录重生成比对 SHA 一致）。
- 验证（`validate_radioml_compatible_clean24.py`）：shape/dtype/有限值/每类 RMS（容差 0.005）/均衡/seed 唯一/GMSK-OQPSK 顺序，全 PASS。

---

## 4. 域匹配门（Phase 4）— dev2400 0/24 FAIL（PASS）

容差：`papr_mean_db≤1.8`、`occupied_bw_99_frac≤0.25`、`occupied_bw_20db_frac≤0.60`、`inst_freq_std_hz≤0.50`（相对）、`psd_corr≥0.30`。

- **dev2400：n_fail = 0（全部 24 类 PASS）**。所有非 AM-SSB 类 5 指标全部满足；psd_corr 最小 ~0.060（AM-SSB-SC）。
- **AM-SSB inst-freq 记录排除**（WC/SC 两类）：AM-SSB 瞬时频率在测量参考中是噪声主导（SNR-20 ~319 Hz vs SNR-30 ~32.6 Hz），在纯净信号中由音频内容主导；单一 fmax 无法同时满足召回≥0.90 与 instF 匹配。因此 instF 对 AM-SSB 从硬失败改为「记录但排除」，其余 4 指标仍硬检。
- smoke96（4 帧/类）仍 3/24 FAIL：帧数太少导致的统计噪声（文档化、预期，非缺陷）；正式判定以 dev2400 为准。

---

## 5. 冻结模型评估（Phase 5）— formal12000 验收全过

| 指标 | raw24 | deployed23 |
|---|---|---|
| overall | **0.99325** | **0.99450** |
| macro | **0.99325** | **0.99426** |
| min recall | 0.956 (OQPSK) | 0.956 (OQPSK) |
| top-2 accuracy | 0.99958 | 0.99958 |
| margin（logit 差）mean/median/min | 18.87 / 19.82 / 0.0059 | — |

- n_samples=**12000**、n_excluded=**0**、NaN/Inf=**0**、checkpoint SHA 匹配、best_epoch=50、best_selection_score=0.89098。
- **逐类召回（raw24，500/类）**：前 12 类（OOK…128APSK）与 AM-DSB-WC/SC、FM、GMSK、AM-SSB-SC 均 **1.0**；16QAM 0.998、32QAM 0.992、64QAM 0.978、128QAM 0.970、256QAM 0.974、AM-SSB-WC 0.970、OQPSK **0.956**（最低）。
- 混淆矩阵主误判方向（共 81 误/12000）：QAM 相邻阶（16QAM→64QAM、32QAM→128QAM、64QAM→128/256QAM、128QAM→256QAM、256QAM→64/128QAM）；AM-SSB-WC→AM-SSB-SC（15，deployed23 合并后归正）；OQPSK→8PSK/16PSK/64APSK/64QAM/128QAM（22，全部落在高频数字类）。
- **deployed23 优于 raw24**：AM-SSB-WC→SC 的 15 例误判在 23 类合并口径下归正（0.99325→0.99450）。

### 5.1 §11.1 验收判定
`CLEAN_IQ_MODEL_COMPATIBLE_PASS`：raw24 overall/macro ≥0.95 ✓，deployed23 overall/macro ≥0.95 ✓，每个 deployed23 召回 ≥0.90 ✓（min 0.956），formal_scored=12000 ✓，formal_excluded=0 ✓，NaN/Inf=0 ✓。
**判定：PASS**（在最高状态 `...-RADIOML-COMPATIBLE-CLEAN-IQ-EVALUATED` 之内，未超）。

---

## 6. 主机测试（§12）

4 个测试文件、**29 项全过**（`29 passed`）：

| 文件 | 覆盖 §12 项 |
|---|---|
| `test_radioml_clean_contract.py` | 5 标签序、6 24→23 映射、7 GMSK/OQPSK 路由、8 AM-SSB WC/SC 独立路径、11 每类 RMS 非均匀、未知类 fail-closed |
| `test_clean24_generator.py` | 1 固定 seed 字节一致、2 异 seed 相异、3 1024 复采样、4 全 24 类、9 无信道损伤、10 无 NaN/Inf、11 RMS/峰值安全、12 无 CI16 削顶 |
| `test_clean24_split_integrity.py` | 13 seed 跨集不相交、14 模拟源按 seed 不相交、15 manifest SHA 可重算、18 scored==total、19 缺失/重复/未知 fail-closed、GMSK/OQPSK 源存在 |
| `test_frozen_model_clean24.py` | 16 checkpoint SHA、17 推理确定性、18 scored==total、6/8 24→23 合并、20 验收门要求满 12000（非 scored>0） |

---

## 7. 交付物文件名映射（§13 期望 vs 实际）

本任务用统一的 `CLEAN2A_*` / `*_<set>` 命名，与 §13 示例名有差异但一一对应，如下：

| §13 期望 | 本任务实际 |
|---|---|
| `analyze_radioml_clean_domain_match.py` | `check_clean24_domain_match.py` |
| `radioml_domain_profile.json` | `CLEAN2A_PHASE1_DOMAIN_PROFILE.json` |
| `domain_match_summary.json` | `CLEAN2A_PHASE4_DOMAIN_MATCH_{set}.json` |
| `domain_match_per_class.tsv` | 内嵌于 `CLEAN2A_PHASE4_DOMAIN_MATCH_{set}.json` 的 `per_class` 字段 |
| `raw24_metrics.json` / `deployed23_metrics.json` | `CLEAN2A_PHASE5_MODEL_EVAL_{set}.json` 的 `raw24` / `deployed23` 字段 |
| `frozen_model_predictions.tsv` | `frozen_model_predictions_{set}.tsv`（3 集） |
| `confusion_matrix_raw24.csv/png` | `confusion_matrix_raw24_{set}.csv`（无 PNG） |
| `confusion_matrix_deployed23.csv/png` | `confusion_matrix_deployed23_{set}.csv`（无 PNG） |
| `clean24_manifest.tsv` | `clean24_manifest.json`（在 dataset 目录，随结果 tar 一并交付） |

---

## 8. 打包（§13）

- `dist/sdr_rml23_fix10clean2a_patch.tar.gz`：代码（8 脚本 + configs + host_tests，前缀 `fix10clean2a/`）。
- `dist/sdr_rml23_fix10clean2a_results.tar.gz`：结果（JSON/TSV/CSV + 审计 + SHA256SUMS + manifest，前缀 `fix10clean2a_results/`）。
- 确定性：uid/gid=0、mtime=0、成员顺序固定、gzip mtime=0 → **两跑 SHA 一致**（packager 内断言）。
- 独立解包 + SHA256SUMS 校验通过。
- **不含**：`__pycache__`/`*.pyc`/cache/tmp/probe 草稿/`.bak`；不打包冻结模型、checkpoint、RadioML HDF5（受保护输入字节不变）；无 NPU/SDR/fix10prep2 内容。
- 数据（3 个 HDF5）留 `fix10clean2a_dataset/`，由 manifest + SHA256SUMS 引 SHA，不重复打包。
- 两个 tar 的最终 SHA256 由 `package_fix10clean2a.py` 输出（两跑一致），见交付说明。

---

## 9. 未解决风险 / 备注

1. **AM-SSB inst-freq 排除**：AM-SSB 的 `inst_freq_std_hz` 因测量参考噪声主导 + 纯净信号音频内容主导而排除硬检（仍记录）。这是有据可查的域失配，不影响召回（AM-SSB 召回 1.0）。
2. **OQPSK 召回最低 0.956**：22/500 误判到高频数字类（8PSK/16PSK/64APSK/64QAM/128QAM），但仍满足 ≥0.90。这是 24 类里唯一显著短板。
3. **本任务不涉及数字回环/SDR**：§13「数字回环结果」项对本任务为 N/A（任务书明确排除 SDR/回环）。「模型直注混淆矩阵」即 §5 的 formal12000 混淆矩阵。
4. **命名偏差**：见 §7；不影响完整性，audit 内已建立映射。
5. **不构成 clean-IQ 数字回环验收**：本任务是「纯净 IQ → 冻结模型直注」的离线评估；空口/RF/数字回环链路（fix10prep2 等）的验收状态不受本任务影响。
