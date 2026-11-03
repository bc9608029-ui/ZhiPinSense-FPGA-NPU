# 基线与契约审计（十二类调制识别鲁棒性增强）

**状态：`READY-FOR-AUTODL-RESULT-INGEST` 之前的离线审计交付物。**
本文件只记录**已核实的基线与契约事实**，不写任何模型性能 PASS，不写根因确认，
不写「某类主因」「某增强参数一定可修复」等 AutoDL 结果回来前无法证实的结论。

---

## 0. 范围与读法

- 审计对象：`F:\FPGA_Work\ad_amr_data_v4_12class_robust\`（由十二类正式基线
  ZIP `ff2b3fb3...` 解包而来，**只读，不再改动**）。
- 对照对象：V1.1 十类基线 `F:\嵌赛\model_ad_amr_v1_1\`（SHA `abe13442...`，只读）。
- 审计结论只回答「基线冻结了什么」；本工程 v4 增强的工作项（`robust_augment.py`、
  结果导入工具、pilot/formal 脚本）均为**新增文件**，未改动基线任何文件。
- 文中 `file:line` 均为基线源文件相对路径与行号（解包后，未改动）。

---

## 1. 基线来源与内容绑定哈希

| 项 | 值 |
|----|----|
| 十二类正式基线 ZIP | `F:\嵌赛\model_ad_amr_v1_2\dist\ad_amr_v1_1_data_v3_12class_autodl.zip` |
| 字节数 | 7,538,546 |
| SHA-256 | `ff2b3fb3661f6b7dd6ae21b20cb78ed1801d300d177dd49b2e4c50053197f044` |
| 解包文件数 | 140（139 个源文件 + `sha256_manifest.txt` 自身） |
| 源清单自校验 | `sha256sum -c sha256_manifest.txt` → **139/139 OK，0 FAILED** |
| V1.1 十类基线 ZIP | `F:\嵌赛\model_ad_amr_v1_1\dist\ad_amr_v1_1_autodl.zip` |
| V1.1 SHA-256 | `abe1344203106f66dc70cb0b0fcd62cf455cec274c798182f30412b4df529096` |

两个 SHA-256 均已与各自 `dist/*.zip.sha256` 侧车文件比对一致（2026-10-05 复算）。
完整 140 文件 SHA 清单见 `BASELINE_FILE_MANIFEST.txt`。

---

## 2. 十二类契约核验

### 2.1 类别顺序（冻结，逐一核对通过）

定义处：`datasets/modulation_generator.py` 的 `V1_1_12_MODULATIONS`。

```
OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM
```

与任务书 §一 冻结顺序**完全一致**。三层强制：

1. 训练入口 `training/train_ad_amr_v1_1_data_v3_12class.py::assert_twelve_class_contract`
   —— 顺序不等于 `V1_1_12_MODULATIONS` 或存在 `class_aliases` 即抛 `RuntimeError`。
2. 数据侧 `datasets/ad_amr_v1_1_dataset.py::assert_v1_1_signal_contract`
   —— 顺序必须在 `{V1_1_MODULATIONS(10), V1_1_12_MODULATIONS(12)}`，且 `sample_length==1024`。
3. 发布门 `scripts/release_guard_v1_1_data_v3_12class.py` 在 preflight 与正式前都校验
   `class_contract` 与 content hash 未变。

`distillation.class_aliases: null`（`configs/ad_amr_v1_1_data_v3_12class.yaml`）——
即 **CPFSK 不被重标为 GFSK**，OOK/4ASK 走监督目标，不走无关教师。

### 2.2 分类头 = 12

- `models/ad_amr_v1_1_net.py::ADAMRV11Net(num_classes=12)`；`build_ad_amr_v1_1_model(len(classes))`
  以 `len(classes)=12` 构造，末层 `Linear(classifier_hidden=128, 12)`。
- 训练结果显式标记：`ten_class_head_reused=False`、
  `architecture_change_scope="classifier output width only: 10 -> 12"`、
  `target_class_count=12`（`training/train_ad_amr_v1_1_data_v3_12class.py`）。
- 硬边界（基线文档 `docs/ad_amr_v1_1_data_v3_12class.md`）：**不加载 10 类 checkpoint**、
  **不在 public test/final blind 上选超参**。

### 2.3 输入契约

| 字段 | 值 | 出处 |
|------|----|------|
| 采样长度 | `sample_length=1024` | `signal.sample_length` + `assert_v1_1_signal_contract` |
| 采样率 | `sample_rate=128000.0` Hz | `signal.sample_rate` |
| 符号率 | `symbol_rate=16000.0` Hz，`sps=8` | `signal` |
| dtype | `float32` | `datasets/ad_amr_dataset.py::to_tensor`（`astype(np.float32)`） |
| IQ 布局 | `[N, 2, 1024]`，第 0 维 real、第 1 维 imag | `np.stack((iq.real, iq.imag))` |
| Q-format | 训练/评估侧为浮点复 IQ，**无定点 Q-format** | —— |
| 归一化 | **per-record RMS 归一化到 amplitude=1.0**，在 `generate_iq` 内、信道增强之前 | `datasets/modulation_generator.py:271-275, 332` |

关键语义：`_normalize_rms` 在 `generate_iq` 末尾（信道之前）做逐记录 RMS 归一化；随后
`channel.ChannelPipeline.__call__` **不再二次 RMS 归一化**，符合「原始记录允许在信道增强前
per-record RMS 归一化，信道增强后禁止再次逐帧 RMS 归一化」的约束。定点 Q1.15 只属于 SDR
适配层（`F:\FPGA_Work\sdr_pluto_board_integration_v1\contracts\rx_iq_format_contract.md`），
不在本训练契约内。

---

## 3. 训练 / 验证 / 测试 / 盲测 边界（泄漏安全）

- **确定性 RNG**：`datasets/ad_amr_dataset.py::ADAMRPairDataset.__getitem__` 以
  `SeedSequence([seed, split_code, epoch, index])` 生成样本 RNG；`split_code =
  blake2s(split_string, 4)`，`sample_id_base = split_code * 1_000_000`。因此同一
  `(seed, split, index)` 的 clean/noisy 记录逐字节一致，不同 split 的 sample_id 区间
  **互不重叠**。
- **禁止访问 public test / final blind**：
  - `datasets/ad_amr_v1_1_dataset.py::FORBIDDEN_SELECTION_TOKENS = ("test", "blind")`；
  - `assert_selection_split(split)` 要求 split 名含 `"validation"` 且不含 `test`/`blind`；
  - `ADAMRV11Dataset.__init__` 遇到 `"blind"` 直接抛错（final blind 数据不可被训练/准备实例化）。
- **评估只走 validation 命名空间**：`evaluation/evaluate_ad_amr_v1_1.py` 的
  `assert_selection_split(split)` 强制；报告内 `final_blind_test_accessed=False` 恒为常量。
- **发布门**：`scripts/release_guard_v1_1_data_v3_12class.py::assert_marker` 重新计算
  内容绑定哈希，若 preflight 后任何源文件、RadioML 数据身份、或 class_contract 变化则拒绝。

---

## 4. 记录级可复现与审计 SHA 的基线映射

任务书 §三 要求审计 `record_manifest / sample_id_order / impairment_param / label_order` 的
SHA。基线**没有单一的 record_manifest 文件**，而是用「确定性生成 + 内容绑定哈希」组合实现。
映射如下：

| 任务书条目 | 基线的对应实现 | 出处 |
|-----------|---------------|------|
| label_order | `signal.modulations`（冻结 12 类顺序），发布门逐次校验 | `configs/ad_amr_v1_1_data_v3_12class.yaml` + `release_guard_v1_1_data_v3_12class.py` |
| sample_id_order | `sample_id = split_code*1e6 + index`，`SeedSequence` 确定性，无跨 split 重叠 | `datasets/ad_amr_dataset.py` |
| impairment_param | 训练域随机范围在 `channel` YAML；OOD 六域规格硬编码在评估代码 | `configs/ad_amr_v1_1.yaml`(channel) + `evaluation/evaluate_ad_amr_v1_1.py::ood_channels` |
| record_manifest | `release_input_hash()`（内容绑定 SHA，覆盖 channel/datasets/models/training/evaluation/scripts/tests/configs/autodl_* + init/*.pt + requirements.txt）+ `sha256_manifest.txt`（139 源文件 SHA）+ RadioML `load_audit`（dataset_sha256/index_sha256） | `scripts/release_guard_v1_1_data_v3_12class.py` |

---

## 5. ONNX 算子白名单与 NPU 边界

- **基线冻结白名单**：`scripts/export_ad_amr_v1_1_onnx.py::ALLOWED_OPS =
  {"Add", "BatchNormalization", "Conv", "Gemm", "ReduceMean", "Relu"}`（**6 个算子**）；
  opset **17**；输出 `ad_amr_v1_1_opset17.onnx`。
- 模型 docstring（`models/ad_amr_v1_1_net.py`）部署图表述为
  「Conv, BatchNormalization, Relu, Add, ReduceMean, Gemm」（**6 个**）。
- 门禁 `unexpected_operators: 0` 与 `onnx_runtime_parity`（max_abs_diff ≤ 0.001）在
  `run_ad_amr_v1_1_data_v3_12class_formal.py` 中执行。

> **ONNX 措辞（任务书 §八，已统一）**：**允许策略 = 6-op**（含 `BatchNormalization`），
> 即 `ALLOWED_OPS = {"Add", "BatchNormalization", "Conv", "Gemm", "ReduceMean", "Relu"}`；
> **实际导出图 = 5-op**（`Add/Conv/Gemm/ReduceMean/Relu`），因为 `torch.onnx.export`
> 在导出时把 `BatchNormalization` **折叠进 Conv**，故导出的 `op_types` 无独立 BN 节点。
> 两句话都对、不矛盾：一个是**白名单策略**（允许 BN），一个是**导出结果**（BN 已折叠）。
> 本工程不修改网络、不修改白名单、不改导出结构；v4 沿用同一 `ADAMRV11Net` 与同一导出脚本。

---

## 6. V1.1 十类基线定位与 SHA

- 路径：`F:\嵌赛\model_ad_amr_v1_1\`；发布 ZIP `dist\ad_amr_v1_1_autodl.zip`，
  SHA `abe1344203106f66dc70cb0b0fcd62cf455cec274c798182f30412b4df529096`。
- 十类顺序（`V1_1_MODULATIONS`）：AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM,
  64QAM, OFDM；`distillation.class_aliases = {CPFSK: GFSK}`（V1.1 有意把旧 CPFSK 教师
  输出当 GFSK）。
- 与十二类的关系：十二类是「RadioML2018.01A 24 类主干预训练 → 12 类合成目标微调」，
  与 V1.1 十类是**两个不同契约**；十二类不加载 10 类 checkpoint，不冒充。

---

## 7. 正式门禁阈值（冻结，全量）

来源：`configs/ad_amr_v1_1.yaml::acceptance.gates` + `configs/ad_amr_v1_1_data_v3_12class.yaml`
新增项；`acceptance.seeds_required=2`。

| 门禁 | 阈值 |
|------|------|
| mean_full_macro_f1 | 0.72 |
| mean_full_accuracy | 0.72 |
| mean_rated_0_20_accuracy | 0.90 |
| mean_high_10_20_accuracy | 0.95 |
| each_seed_snr_0_accuracy | 0.85 |
| each_seed_min_rated_class_accuracy | 0.75 |
| each_seed_new_ask_rated_accuracy | 0.75（十二类新增，OOK/4ASK 双种子每类） |
| max_ood_macro_f1_drop | 0.08 |
| onnx_max_abs_diff | 0.001 |
| fake_int8_accuracy_drop | 0.03 |
| unexpected_operators | 0 |

正式配置：`data_v3_formal.seeds=[2026,2027]`、`epochs=100`、`minimum_epochs_before_stopping=30`。

---

## 8. OOD 域定义（评估侧）

来源：`evaluation/evaluate_ad_amr_v1_1.py::ood_channels`（硬编码，非 YAML）。每个域
`domain_randomization=False`，除 `awgn(prob 1.0)` 与被命名的效果(prob 1.0)外全部关闭。

| 域 | 效果与范围 |
|----|-----------|
| `cfo_strong` | cfo `hz [-2500, 2500]` |
| `phase_noise` | phase_noise `std_rad [0.004, 0.012]` |
| `iq_imbalance` | `gain_db [-2.0, 2.0]`, `phase_deg [-10.0, 10.0]` |
| `multipath` | `num_taps [3, 6]`, `max_delay 20` |
| `clipping` | `level_rms [0.8, 1.4]` |
| `multi_impairment` | cfo `[-1800,1800]` + phase_noise `[0.002,0.008]` + iq_imbalance `[-1.5,1.5]/[-8,8]` + multipath `num_taps [2,5]` `max_delay 16` |

用户已确认正式评估的失败大类为 **`cfo_strong` / `multipath` / `multi_impairment`**（其余
域与正常验证、额定 SNR、0 dB、伪 INT8、ONNX 白名单、ORT 一致性均通过）。本审计不展开
「具体脆弱类别 / 混淆关系 / 根因」——这些只能等 AutoDL 正式结果包确认。

---

## 9. 审计发现与待核对项（只记录，不擅自改）

1. **ONNX 白名单措辞**：允许策略 6-op（含 BatchNormalization）vs 实际导出 5-op（BN 导出时
   折叠进 Conv），两句话不矛盾，见 §5。
2. **混淆矩阵/逐样本预测未落盘**：`training/metrics.py::classification_metrics` 计算了
   `confusion_matrix`，但 `training/ad_amr_v1_1_trainer.py::_summary` 与
   `evaluation/evaluate_ad_amr_v1_1.py::evaluate_v1_1` 未把 `confusion_matrix` 或逐样本
   预测写入评估报告 → 基线 `acceptance.json` 只有聚合指标，**无法直接做「混淆关系」分析**；
   所需补充产物清单见 `docs/NEEDS_AUTODL_RESULTS.md`。
3. **OOD 域规格硬编码在评估代码**（`ood_channels`），不在 YAML → 这正是 v4 通用增强模块
   （`channel/robust_augment.py` + 模板 YAML）要参数化的对象；v4 仅新增文件，不改基线评估。
4. **record_manifest 无独立文件**，以 release hash + 源文件 SHA + RadioML audit 组合实现（§4）。

---

## 10. 结论

- 十二类顺序、head=12、输入 1024、IQ float32 `[N,2,1024]`、归一化位置（生成侧 per-record
  RMS，信道侧不再归一化）、split 隔离（禁 test/blind）、门禁阈值、OOD 六域均已**逐一核实**，
  与任务书 §一/§三 一致（唯一措辞差异见 §5、§9.1）。
- 基线 ZIP 与 V1.1 ZIP 的 SHA 已复算一致；140 文件解包清单自校验全 OK。
- 本审计**不写任何模型性能 PASS / 根因 / 脆弱类别 / 混淆关系**；这些留待 AutoDL 正式结果
  包，由 `scripts/import_formal_results.py` + `scripts/analyze_formal_failures.py` +
  `scripts/verify_paired_records.py` 在结果回来后再处理。
