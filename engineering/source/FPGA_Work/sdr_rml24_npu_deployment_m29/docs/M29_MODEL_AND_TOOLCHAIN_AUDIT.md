# M29 — RML2018 24 类模型 NPU 部署：模型与环境审计（Phase A）

状态：`M29-PHASE-C-INT8-CALIBRATION-COMPLETE`（A 身份核验 + B ONNX 导出 + C 校准/fake-INT8 全绿，未碰板/未写 Flash/未访问 test）

本文冻结 M29 部署的**权威输入、身份核验结果、契约、算子清单与工具链现状**，作为后续
ONNX 导出 → INT8 校准 → ZG330 编译 → 板测包的唯一事实来源。所有 SHA 本机实测。

---

## 一、权威输入

| 项 | 路径 / 值 |
|---|---|
| 冻结产物包 | `F:\FPGA_Work\24class_results\rml24_final_artifacts.tar.gz`（SHA `0b2b7c2a…`，sidecar 一致） |
| 权威 checkpoint | `F:\FPGA_Work\24class_results\rml24_seed2027_best.pt`（== 包内 `runs/.../seed2027/checkpoints/best.pt`，SHA 相同） |
| 冻结源（本机解包） | `_frozen/{contracts,models,evaluation,configs,runs}` |
| 训练源码树（只读参照） | `F:\FPGA_Work\sdr_amr_rml24_ood_v1_1`（与冻结包逐文件 SHA 一致，见 §二） |
| 数据集 HDF5（本机） | `F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5`（21.4 GiB） |
| 12 类部署参照（镜像流水线） | `F:\FPGA_Work\sdr_full_chain_12class_v1\model_12class\` |

冻结包解压时 `tar` 报 `Cannot utime`（Windows 时间戳回填失败），**内容完整**（checkpoint SHA
`96cd25f8…` 与包外同名文件一致，契约文件与 v1_1 树逐字节一致）。

---

## 二、身份核验结果（fail-closed，`scripts/verify_m29_identity.py` 实测）

| 身份 | 期望 | 实测 | 结果 |
|---|---|---|---|
| checkpoint SHA256 | `96cd25f8…` | `96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d` | **PASS** |
| label_contract_sha256 | `3e1382d1…` | `3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549` | **PASS**（由冻结 `LABEL_ORDER_24` 重算） |
| dataset_sha256 | `e3dd0bef…` | `e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38`（本地 HDF5 实测，21,449,148,312 B） | **PASS** |
| config_sha256 | `edbe6e01…` | `edbe6e01a314239eab05c6126dc74f989f9a6b25031a26bb73b806a73e1d56c1` | **PASS**（由 base+candidate 复算） |
| model_name | `RML2018_24_BENCHMARK` | `RML2018_24_BENCHMARK` | **PASS** |
| class_count | 24 | 24 | **PASS** |
| checkpoint.class_names == LABEL_ORDER_24 | 逐序一致 | MATCH | **PASS** |
| 架构严格加载 | strict load | `load_state_dict(strict=True)` OK，参数 **280,584** | **PASS** |
| checkpoint epoch / selection | — | epoch=50 / best_epoch=50 / best_selection_score=`0.890984…` / loss=`cross_entropy` | 记录 |

**candidate_signature**（训练去重身份）实测为 `cb7c6771…`，与 manifest `b8772046…` 不一致：
根因 = `canonical_candidate_signature` 绑定 `split_sha256`（split index `.npz` 在 AutoDL 上重新生成、
其文件 SHA 会漂移），而 `config_sha256`（不含 split）已复算一致，证明训练面完全一致。此为**训练
溯源身份**，非部署身份——部署所需身份（checkpoint/标签序/架构/数据集）均已独立核验，故**不 fail-closed**，
仅记录。

---

## 三、冻结契约（权威）

```python
LABEL_ORDER_24 = ("OOK","4ASK","8ASK","BPSK","QPSK","8PSK","16PSK","32PSK",
                  "16APSK","32APSK","64APSK","128APSK","16QAM","32QAM","64QAM",
                  "128QAM","256QAM","AM-SSB-WC","AM-SSB-SC","AM-DSB-WC",
                  "AM-DSB-SC","FM","GMSK","OQPSK")
INPUT_SHAPE = (1, 2, 1024)   # fp32, planar [real, imag], RMS ~1.0（数据已归一化，模型不重缩放）
OUTPUT_DIM  = 24
OUTPUT_KIND = "raw_logits_no_softmax"
```

- 输入域：raw I/Q `[1,2,1024]`，channel 0 = I、channel 1 = Q，**训练域 RMS=1.0**；预处理（RMS 归一化）
  在 dataloader，**不在模型图内**（`ADAMRV11Net.forward(iq) = classifier(features(denoiser(iq)).mean(-1))`）。
- 输出域：raw logits `[1,24]`（无 softmax）。
- 标签序来源：冻结 `contracts/rml24_contract.py::LABEL_ORDER_24`，与 `rml2018_data_contract.json::class_names`
  逐序一致；checkpoint `class_names` 同序。

---

## 四、模型架构与算子清单（`artifacts/m29_operator_inventory.json`）

`ADAMRV11Net`（`models/ad_amr_v1_1_net.py`，NPU 可部署 student）：

```
denoiser : stem Conv1d(2→24,k7,p3)+BN+ReLU → 3× ResidualUnit(24,24)
           → correction Conv1d(24→2,k5,p2) → out = iq + correction
features : 4 stages × [ ResidualUnit(stride=2) + ResidualUnit(stride=1) ],
           channels [32,48,64,96] → .mean(dim=-1)
classifier: Linear(96→128)+ReLU+Dropout(0.15)+Linear(128→24)
```

| 算子 | 图级别计数 | 说明 |
|---|---|---|
| Conv1d | **28** | 全部 bias=False；kernel/stride 见 inventory JSON |
| BatchNorm1d | **27** | — |
| ReLU | **24**（图） | 每个 ResidualUnit 的单一 `nn.ReLU` 在 forward 被调用两次（bn1 后 + 残差加后）；13 个 module |
| Add | **12** | 11 个残差加 + 1 个 denoiser `iq+correction` |
| Linear(Gemm) | **2** | 96→128、128→24 |
| ReduceMean | **1** | `features.mean(dim=-1)` |
| Dropout | **1** | eval/导出时恒等 |

算子策略与 12 类部署一致：**Conv / BatchNormalization / Relu / Add / ReduceMean / Gemm only**，无
Resize/Sigmoid/Abs/Sign、无 softmax。参数总数 **280,584**（fp32 ≈ 1.07 MiB；int8 权重 ≈ 274 KiB）。

> 交叉验证：本架构与 12 类 `MODEL_DEPLOYMENT_CONTRACT.md` 记录的算子清单（Add 12 / Conv 28 / Gemm 2 /
> ReduceMean 1 / Relu 24）**完全一致**，仅末层 Linear 输出 12→24。

---

## 五、工具链审计

| 工具 | 版本 / 路径 | 用途 | 状态 |
|---|---|---|---|
| Python | 3.13.5（`D:\Anaconda\python.exe`） | 导出/校准/核验 | 可用 |
| PyTorch | 2.12.0+cpu | 加载 checkpoint、导出 ONNX | 可用 |
| onnx | 1.23.1 | 模型检查 / shape inference | 可用 |
| onnxruntime | 1.30.0（CPU） | PyTorch↔ONNX 一致性 | 可用 |
| numpy / yaml | 2.1.3 / 6.0.2 | 校准数据 / 配置 | 可用 |
| h5py | 待确认 | 读取 HDF5 验证集 | 待确认 |
| **iCraft CLI** | **v3.39.0** `C:/Icraft/CLI v3.39.0/bin/icraft.exe` | ZG330 编译（parse→optimize→quantize→adapt→generate） | 可用 |
| HDF5 数据集 | `F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5`（21.4 GiB） | validation-only INT8 校准 | 本机可用 |

`python -I`（隔离模式）会剥离 user site-packages（torch/onnx 所在），脚本在 `sys.path` 显式回加
`C:\Users\shado\AppData\Roaming\Python\Python313\site-packages`；checkpoint 用 `torch.load(weights_only=True)`
加载，不执行 pickle 代码。

---

## 六、镜像参照（12 类部署流水线，M29 复刻）

12 类已跑通的 NPU 编译流水线（`sdr_full_chain_12class_v1/model_12class/`）即 M29 的模板：

1. **ONNX 导出**：opset 17 / IR 8，单输入 `iq[1,2,1024]` fp32 → 单输出 `logits[1,N]`。
2. **iCraft 编译**：`parse → optimize → quantize → adapt → generate`，target=`zhuge`/`ZHUGE`/`@zhuget(330)`。
3. **量化**：`qdtype=int8, bits=8, saturation=kld, per=channel, no_transinput=true, no_imagemake=true`；
   输入保持 fp32，输出反量化自动，板端喂 fp32、读 fp32。
4. **校准集**：`cal_data/iq_N.bin`（每条 8192 B = `[2,1024]` fp32 C 序：先 1024 I 再 1024 Q）+ `forward_list.txt`。
5. **产物**：`model_12class.json`（网络描述）+ `.raw`（权重），板端加载。

**M29 差异**：24 类、末层 128→24；校准集改为**真实 RadioML2018 validation split**（`validation-only`，
`禁止用 test`），样本数按 24 类分层。

---

## 七、红线（本任务全程）

- **我禁碰板 / 禁写 Flash**；不代替用户做真实上板测试、JTAG 或 Flash 写入。
- 禁止重新训练/微调模型；禁止再次访问闭集 **test**（`rml24_closed_set_final.json` 已记录
  `final_blind_test_accessed: true`，`ood_final_test_accessed: false`）；禁止用 test 校准 INT8；
  禁止用最终测试指标选择量化参数。
- 禁止每帧重新 Open/Load/Compile NPU 模型（单模型常驻）。
- 不得修改模型、标签序、预处理、RTL、XDC、位流、SDR 数据链、NPU 核心推理逻辑。
- 禁写标记：`NPU_PASS` / `24CLASS_SYSTEM_PASS` / `24CLASS_PASS` / `FINAL_PASS` / `FINAL_24CLASS_PASS` /
  `OOD_PASS` / `HARDWARE_PASS` / `FULL_CHAIN_PASS` / `PROJECT_COMPLETE` / `FINAL_*`。
- **最高离线状态：`M29-RML24-NPU-OFFLINE-PACKAGE-READY`**（真实 RF 闭环 + UI 验证前不写任何 PASS 族）。

---

## 八、Phase B/C 阶段结果（ONNX 导出 + INT8 校准 + fake-INT8）

### 8.1 Phase B — ONNX 导出（`work/onnx/rml24_24class_opset17.onnx`）

| 项 | 值 |
|---|---|
| opset / IR | 17 / 8 |
| 输入 / 输出 | `iq` `[1,2,1024]` fp32 → `logits` `[1,24]` fp32 |
| 算子 | Add(12) / Conv(28) / Gemm(2) / ReduceMean(1) / Relu(24)（BatchNorm 已折叠进 Conv） |
| 算子门禁 | 仅允许 Conv/BatchNormalization/Relu/Add/ReduceMean/Gemm，无越界算子 |
| ORT↔PyTorch 一致性 | zeros `max_abs_diff 3.662e-4`、random `7.629e-5`（阈值 1e-3，全过） |
| shape inference | `[1,24]` ✓ |

与 12 类契约算子清单（Add 12 / Conv 28 / Gemm 2 / ReduceMean 1 / Relu 24）**完全一致**，仅末层
Linear 输出 12→24。

### 8.2 Phase C1 — validation-only INT8 校准（`work/calibration/`）

| 项 | 值 |
|---|---|
| 样本数 | **624 = 24 类 × 26 SNR × 1**（每 (类,SNR) 层各 1 条；validation 每层有 819 条） |
| split | `radioml2018_validation`（**未触碰 test**，`test_split_touched=false`） |
| seed | 2027（固定 RNG 每层洗牌取 1） |
| 输入域 | raw planar I/Q `[2,1024]` fp32，8192 B/条（C 序：先 1024 I 再 1024 Q），字节与模型输入一致 |
| 输出 | `cal_data/iq_0.bin … iq_623.bin` + `forward_list.txt`（单列）+ `calibration_manifest.json` |
| forward_list SHA256 | `cb38169cebc73fd93066c2ff417273958ad42cf24890a9df291b0ad8700dea1b` |
| fail-closed 门禁 | HDF5 SHA `e3dd0bef…`（全量 21.4 GiB 哈希）✓ + index SHA `9a035841…` ✓ |

### 8.3 Phase C2 — fake-INT8 vs fp32（`work/fake_int8/fake_int8_report.json`）

fake-INT8 = 对称 per-tensor 权重量化（scale=max|w|/127，clamp [-127,127]，激活保持 fp32），逐字复刻
`_frozen/evaluation/evaluate_rml24.py::_apply_fake_int8`。在 131072 条分层 validation 子集上对 fp32
与 fake-int8 各跑一遍 top-1。

| 指标 | fp32 | fake-int8 | Δ |
|---|---|---|---|
| accuracy | 0.629921 | 0.628052 | **−0.001869**（−0.19pp） |
| rated_0_20_accuracy | 0.889632 | 0.888135 | **−0.001497**（−0.15pp） |
| min_per_class_accuracy | 0.515201 | 0.509341 | −0.005860 |
| selection_score | — | — | −0.0017 级 |
| max per-class drop | — | — | −0.032601（单类最差） |

> 交叉验证：fp32 `accuracy 0.629921` 与闭集最终评估记录的 `0.630457` 一致（子集抽样噪声内）；
> fp32 `rated_0_20 0.889632` 与 checkpoint 记录 `0.890998`（全量 validation）一致。fake-INT8 仅权重
> 量化（不含激活量化），精度损失 ≤0.19pp，为后续 vendor INT8（KLD per-channel 权重+激活）提供上界参照。

---

## 九、阶段产物

| 阶段 | 产物 | 状态 |
|---|---|---|
| A 审计 | `docs/M29_MODEL_AND_TOOLCHAIN_AUDIT.md`、`artifacts/m29_model_identity.json`、`artifacts/m29_operator_inventory.json` | **完成** |
| B ONNX | `work/onnx/rml24_24class_opset17.onnx` + 一致性报告 | **完成** |
| C 校准 | `work/calibration/`（validation-only 624）+ fake-INT8 比较 | **完成** |
| D 编译 | `work/compile/` iCraft 产物（parse/optimize 完成，quantize 进行中） | 进行中 |
| E probe | `work/probe/` 独立板端 probe（脚本+黄金集，不碰板） | 待做 |
| F 板测包 | `dist/m29_rml24_npu_board_package.tar.gz` | 待做 |
