# V1 基线冻结（任务：十二类调制识别模型 V2 鲁棒性改进 · 阶段四 / Phase 1）

> 状态：**基线冻结完成（只读，未改动任何上游资产）**。
> 日期：2026-10-07。新建工程：`F:\FPGA_Work\ad_amr_12class_robust_v2`。
> 冻结源（只读，绝不修改）：
> - 训练源 `F:\嵌赛\model_ad_amr_v1_2`（V1.1 data-v3 十二类，与结果快照逐字节一致，见 §6）
> - 结果快照 `F:\FPGA_Work\_tmp_ad_amr_results_verify\ad_amr_data_v3_12class_ff2b3fb3_run`
> - 部署产物 `F:\FPGA_Work\sdr_full_chain_12class_combined_v1\model_12class\`（json/raw + 部署契约）

---

## 0. V1 身份

| 项 | 值 |
|---|---|
| 模型标签 | **`12CLASS_CHAIN_VALIDATION_MODEL`**（本任务规范中记作 `12CLASS_CHAIN_VALIDATION_MODEL_V1`） |
| 部署产物 | `model_12class.raw`（SHA `2ae95275…`，全量见 §6） |
| 定位 | 十二类 SDR→FPGA/NPU→UI 链路的**通路验证模型**，**非**最终鲁棒模型 |
| OOD 门 | **NO_GO**（源工程 `acceptance.json` `ood_macro_f1_drop` 未过，见 §7） |
| 类别数 | 12（冻结顺序，见 §1） |

> 措辞红线：任何报告不得把本模型写成「最终鲁棒模型 / 最终准确率 PASS / OOD PASS」。

---

## 1. 冻结标签（12 类权威顺序）

| idx | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 类 | OOK | 4ASK | AM-DSB | WBFM | 2FSK | GFSK | BPSK | QPSK | 8PSK | 16QAM | 64QAM | OFDM |

来源 = `sdr_adapter/categories.hpp` `cat::target_12()`，与训练 `class_contract` 逐位一致。

---

## 2. 数据版本与来源（冻结）

| 项 | 值 |
|---|---|
| 数据版本 | **data-v3（十二类）**：在 data-v2（十类）基础上新增 **OOK + 4ASK**，精确名蒸馏（`class_aliases: null`，**不**把 CPFSK 改标成 GFSK） |
| 训练源包 | `F:\嵌赛\model_ad_amr_v1_2\dist\ad_amr_v1_1_data_v3_12class_autodl.zip`（7,538,546 B，SHA `ff2b3fb3661f6b7dd6ae21b20cb78ed1801d300d177dd49b2e4c50053197f044`） |
| release_input_hash | `5acf4358e352bcbaee3d124f9a9ad82dccc114a59f7c5bd744d74a0edd5f1ef7` |
| variant（正式） | `radioml_pretrained`（RadioML2018.01A 公开预训练 → 十二类合成数据微调） |
| 上游源文件清单 | 见 `BASELINE_SOURCE_SHA256.txt`（本工程根目录） |

数据域（与 V2 四域对照，V1 仅覆盖 D1/D2/D3）：

| 域 | V1 基线现状 |
|---|---|
| D1 合成训练 | 程序化生成（`datasets/modulation_generator.py` + `channel/channel_pipeline.py`），非落盘文件；食谱+种子+源码 SHA 见 `BASELINE_DATA_MANIFEST.txt` |
| D2 冻结合成测试 | 同上程序化：val 7560 + 每 OOD 域 2520（6 域） |
| D3 公开数据 | RadioML2018.01A（`classes.txt`/`README.md` 落盘；HDF5+split_indices+audit 在 AutoDL 运行时下载） |
| D4 真实 Pluto RF | **V1 无**（V2 目标域，当前 `NEEDS-REAL-RF-DATA`） |

---

## 3. 训练配置（冻结）

### 3.1 信号契约（`configs/ad_amr_v1_1.yaml`，data-v3 继承）

| 项 | 值 |
|---|---|
| 采样率 / 符号率 | 128,000 Hz / 16,000 Hz |
| samples_per_symbol / sample_length | 8 / 1024 |
| 幅度 / 频偏 / 相偏 | 1.0 / 0.0 / 0.0 |
| 脉冲成形 | RRC，rolloff 0.35，span 8 |
| AM-DSB | index [0.35, 0.9]，msg BW [2500, 7000] Hz |
| WBFM | dev [10000, 22000] Hz |
| GFSK | BT [0.3, 0.7]，mod_index [0.45, 0.55]，span 4 |
| OFDM | FFT 256 / CP 64 / 活跃子载波 48 / 子载波 QPSK |
| 调制集（12 类） | OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM |

### 3.2 信道（域随机化）

AWGN snr[-20,20]dB（prob 1.0）；Rayleigh 0.10；Rician 0.10（K[3,10]）；multipath 0.12（2–4 taps，max_delay 10）；CFO 0.55（±1200 Hz）；相偏 0.65；相位噪声 0.10（std[0.0001,0.003] rad）；SFO 0.08（±60 ppm）；IQ 不平衡 0.12（gain ±1 dB，phase ±5°）；DC 偏置 0.08；幅度缩放 0.5（0.7–1.3）；clipping 0.06（1.5–2.5 RMS）。窄带/突发干扰关闭。

### 3.3 数据集

| 项 | 值 |
|---|---|
| train_samples / val_samples | 37800 / 7560（精确平衡：21 SNR × 12 类 × 150/30 重复） |
| snr_values | [-20, -18, …, 18, 20]（21 点，步 2 dB） |
| ood_samples | 2520（每 OOD 域） |

### 3.4 模型结构参数

`denoiser_channels=24`，`denoiser_blocks=3`，`feature_channels=[32,48,64,96]`，`classifier_hidden=128`，`dropout=0.15`。

### 3.5 训练超参（data-v3 正式）

| 项 | 值 |
|---|---|
| seeds | [2026, 2027]，epochs 100，minimum_epochs_before_stopping 30 |
| batch_size / lr / weight_decay | 128 / 0.001 / 0.0001 |
| amp | true，bfloat16 |
| reconstruction_weight | 0.02 |
| 蒸馏 | enabled，temp 3.0，v2_weight 0.15，v1_weight 0.25，`class_aliases: null`（data-v3 覆盖） |
| snr_weighting | very_low 0.35 / rated 1.25 / zero_db_extra 1.20 |
| 公开预训练 | epochs 30，batch 256，lr 0.001，RadioML2018.01A（24 类 trunk） |

### 3.6 验收门限（冻结，data-v3 保留十类门 + 新增 ASK 门）

| 门 | 阈值 |
|---|---|
| mean_full_macro_f1 | 0.72 |
| mean_full_accuracy | 0.72 |
| mean_rated_0_20_accuracy | 0.90 |
| mean_high_10_20_accuracy | 0.95 |
| each_seed_snr_0_accuracy | 0.85 |
| each_seed_min_rated_class_accuracy | 0.75 |
| each_seed_new_ask_rated_accuracy | 0.75（data-v3 新增，OOK/4ASK 显式下限） |
| max_ood_macro_f1_drop | 0.08 |
| fake_int8_accuracy_drop | 0.03 |
| onnx_max_abs_diff | 0.001 |
| unexpected_operators | 0 |

---

## 4. 模型结构（`models/ad_amr_v1_1_net.py` → `ADAMRV11Net`）

- **DeployableResidualDenoiser**（形状保持，无 Resize/Sigmoid/Abs/Sign）：
  stem `Conv1d(2→24,k7,p3)`+BN+ReLU → 3×`ResidualUnit(24,24)` → correction `Conv1d(24→2,k5,p2)`；
  输出 `iq + correction`（残差去噪）。
- **features**：4 级，每级 `ResidualUnit(in→ch, stride=2)` + `ResidualUnit(ch→ch, stride=1)`，ch=[32,48,64,96]。
- **classifier**：`Linear(96→128)` + ReLU + Dropout(0.15) + `Linear(128→12)`。
- **forward**：`denoised = denoiser(iq)` → `features = features(denoised).mean(dim=-1)` → `classifier(features)`。
- **ResidualUnit**：`conv1(k5)+bn1+relu` → `conv2(k3)+bn2` → `relu(out+residual)`（stride≠1 或通道变化时加 1×1 投影）。

| 项 | 值 |
|---|---|
| 参数（12 类） | **279,036**（trainable 279,036；neural_macs 46,544,384；fp32 参数 ~1.064 MB） |
| 输入 / 输出 | `iq[N,2,1024]` fp32（ch0=I, ch1=Q）→ `logits[N,12]` fp32 |
| 算子白名单 | Conv / BatchNormalization / Relu / Add / ReduceMean / Gemm（BN 折叠后 ONNX 仅 5 类算子） |
| ONNX opset / IR | 17 / IR 8 |

---

## 5. 随机种子（冻结）

| 项 | 值 |
|---|---|
| 正式训练 seeds | [2026, 2027] |
| 公开数据 split_seed | 20261003（split_ratios 0.60/0.20/0.20） |
| 量化校准集 | seed 2026，split_code = blake2s("ad_amr_v1_1_train")[:4]，RNG 复刻 `SeedSequence([seed, split_code, 0, index])` |
| 数据集切分 | 按来源切分（非随机窗口），`FORBIDDEN_SELECTION_TOKENS` 防泄漏（见 `BASELINE_DATA_MANIFEST.txt`） |

---

## 6. 冻结产物 SHA256（本机实测）

### 6.1 正式 checkpoint（结果快照 `outputs/ad_amr_v1_1_data_v3_12class/formal/`）

| 文件 | 字节 | SHA256 |
|---|---|---|
| `seed2026/checkpoints/best.pt` | 3,504,977 | `7215290b0f43f8a8cc05f4ee135f2a9524cf8a8036b71ae52b0b6c94c02aae72` |
| `seed2026/checkpoints/last.pt` | 3,513,873 | `20a9fe8cf2b246e9688c7e3533909ccead21897526e4d4bbe76fbf7de7f02991` |
| `seed2027/checkpoints/best.pt` | 3,510,161 | `aa0d573fc9adf53a0ffd15817727b7f1cf3554a4924bedb46abf818b919197c2` |
| `seed2027/checkpoints/last.pt` | 3,519,057 | `3d1bd748b13282ce783f91314518d0f6c94a4cb743176dfaee26dad32028a91b` |

### 6.2 源 ONNX（正式导出，seed2026/best.pt，checkpoint_epoch=22）

| 文件 | 字节 | SHA256 |
|---|---|---|
| `formal/export/onnx/ad_amr_v1_1_opset17.onnx` | 1,126,095 | `f77587152b52cda9a467b28790bc62d0eb0c639db2c39da82642c00ca8deda5a` |
| `formal/export/onnx/export_report.json` | 1,139 | `de8a37a14883f1f41ff6d41f498ecc0c9399c7c3346302f01d04cf381745e752` |

### 6.3 部署产物（iCraft v3.39.0，@zhuget(330)，INT8 对称 per-channel KLD，no_transinput）

| 文件 | 字节 | SHA256 |
|---|---|---|
| `model_12class/model_12class.json` | 222,804 | `51364bdf49d280944094f7af89ea4c759b3ae4d0d350be5f8c43e0c5849ab834` |
| `model_12class/model_12class.raw` | 2,851,472 | `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c` |
| `model_12class/model_12class.sha256` | 84 | `fbdaf1ac3849b487a28cc6f05eeea06463d383257a4a3053bcb16cb1ffede7ba` |
| `model_12class/MODEL_DEPLOYMENT_CONTRACT.md` | 7,767 | `ef4c32b4b97db6820494e520baa0482da5b6d90c019652619cb62a2b8657db67` |

### 6.4 正式验收 / 侧车

| 文件 | 字节 | SHA256 |
|---|---|---|
| `formal/acceptance.json`（结果快照） | 206,878 | `fc9b359a1c071b25a842da0abd4771f61170b3d830bd65bad81bee4e8f8a3bc0` |
| `deployment_golden/manifest.json` | 980 | `81592ef13495a1d99fdee31ed6e8ce35db857816c16538c2db0627d288164b7c` |
| `model_12class/calibration/calibration_manifest.json` | 35,638 | `c073f92663cf37c677c7341a71491d2d3c48fd5aaa54866aa3d7b6a7e2dfa078` |
| `model_12class/calibration/forward_list.txt` | 2,914 | `6419217933670dd883ecdbd78a6ffb2628ebc1f9923d0834390514648e07658d` |

> 全部源文件 SHA 见 `BASELINE_SOURCE_SHA256.txt`（含逐文件清单）。

---

## 7. V1 当前结果（冻结：ID / OOD / fake-int8 / golden）

### 7.1 门禁汇总（`acceptance.json`，variant=radioml_pretrained）

| 门 | 结果 | 阈值 | 判定 |
|---|---|---|---|
| two_seeds_complete | 2 | 2 | PASS |
| mean_full_macro_f1 | 0.736574 | 0.72 | PASS |
| mean_full_accuracy | 0.736706 | 0.72 | PASS |
| mean_rated_0_20_accuracy | 0.963384 | 0.90 | PASS |
| mean_high_10_20_accuracy | 0.982870 | 0.95 | PASS |
| each_seed_snr_0_accuracy | 2026=0.886111 / 2027=0.9 | 0.85 | PASS |
| each_seed_min_rated_class_accuracy | 2026=0.854545 / 2027=0.836364 | 0.75 | PASS |
| each_seed_new_ask_rated_accuracy | OOK/4ASK 全部 ≥0.9939 | 0.75 | PASS |
| **ood_macro_f1_drop** | 见 7.2 | 0.08 | **FAIL** |
| fake_int8_accuracy_drop | 2026=0.008862 / 2027=0.000397 | 0.03 | PASS |
| onnx_operator_whitelist | opset 17，Add 12/Conv 28/Gemm 2/ReduceMean 1/Relu 24 | 0 unexpected | PASS |
| onnx_runtime_parity | max_abs_diff 5.4836e-6 | 0.001 | PASS |
| public_and_final_blind_untouched | 均 false | — | PASS |

### 7.2 OOD 宏 F1 下降（失败域，唯一 NO_GO 门）

| 域 | seed2026 drop | seed2027 drop | 判定（>0.08） |
|---|---|---|---|
| cfo_strong | 0.126874 | 0.122186 | **FAIL** |
| multipath | 0.120682 | 0.114814 | **FAIL** |
| multi_impairment | 0.133181 | 0.131168 | **FAIL** |
| phase_noise | -0.027303 | -0.023480 | pass（噪声域无退化） |
| iq_imbalance | -0.023850 | -0.018852 | pass |
| clipping | 0.028364 | 0.027644 | pass |

> 主退化类（failure_analysis 排名）：cfo_strong 退化 2FSK/GFSK/AM-DSB/QPSK/BPSK；multipath 退化 16QAM/8PSK/QPSK/BPSK；multi_impairment 退化 16QAM/QPSK/8PSK/BPSK。**V2 鲁棒性改进聚焦这三个失败域。**

### 7.3 fake-int8（对称 INT8 权重 / fp32 激活）

| seed | accuracy | macro_f1 | drop |
|---|---|---|---|
| 2026 | 0.726720 | 0.727942 | 0.008862 |
| 2027 | 0.737434 | 0.736571 | 0.000397 |

### 7.4 部署黄金集

- 240 条（12 类 × 20，SNR 固定 10 dB），`deployment_golden/`（`expected_logits_or_argmax.json` 等）。
- argmax 与标签自洽 **236/240 (98.3%)**（10 dB 高 SNR 下接近满，证明域/顺序正确）。

---

## 8. 可复现性判定（对应「无法复现先查明差异」）

**一致性链已逐级核验，无差异：**

1. **源码一致**：`F:\嵌赛\model_ad_amr_v1_2` 与结果快照 `…_ff2b3fb3_run` 的关键 V1.1 十二类源文件 SHA 逐字节一致（17 个关键文件全 `SAME`，见 `BASELINE_SOURCE_SHA256.txt`）。
2. **ONNX←checkpoint**：`export_report.json` 声明 ONNX 由 `seed2026/checkpoints/best.pt`（epoch 22）导出；其 op 统计与 `acceptance.json` 的 `onnx_operator_whitelist` 完全一致。
3. **raw←ONNX**：`MODEL_DEPLOYMENT_CONTRACT.md` 源 ONNX SHA `f7758715…` 与实测正式导出 ONNX 一致；编译产物 json/raw SHA 与部署契约一致。
4. **结果一致**：`imported_results.json`（v4 工程回传）与结果快照 `acceptance.json` 的 source 路径一致，门禁数值逐项吻合。

**复现条件**：完整重训需 AutoDL/CUDA（本机无 GPU，合成数据程序化生成）。复现命令链：`setup_env.sh → run_data_audit.sh → run_public_pretrain.sh → run_pilot.sh → run_formal.sh`（`autodl_ad_amr_v1_1_data_v3_12class/` 内脚本）。**离线本机已确认链路一致、无差异；重训复现在 AutoDL 执行。**

---

## 9. 状态红线

- 本工程只标 V2 规范允许的状态；未经实机/AutoDL 验证**绝不**写 `FINAL_MODEL_PASS / ROBUST_MODEL_PASS / REAL_RF_PASS / OOD_PASS / PROJECT_COMPLETE`。
- V1 冻结产物（checkpoint/ONNX/json/raw）**只读**，不覆盖；新模型仅命名 `12CLASS_ROBUST_CANDIDATE_V2`。
- 我禁碰板、禁写 Flash；上板由用户本人执行。
