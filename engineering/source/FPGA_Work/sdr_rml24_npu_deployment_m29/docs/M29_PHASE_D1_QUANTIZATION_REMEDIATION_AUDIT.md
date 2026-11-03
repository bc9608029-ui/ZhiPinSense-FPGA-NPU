# M29 Phase D.1 — 24类量化敏感层整改 · 只读审计报告

- 工程：`F:\FPGA_Work\sdr_rml24_npu_deployment_m29\`
- 状态：`M29-RML24-NPU-QUANTIZATION-REMEDIATION_REQUIRED`
- 目标：定位并整改 Phase D（384 校准）精度门失败（min_class −32.8pp，AM-SSB-SC 51.6%→7.8%）的**量化敏感层**，在不改模型结构、不重训、不改标签序、不碰板的前提下，用官方支持的混合精度语义对输出层/分类头做更高位宽整改。
- 本报告为**只读审计**结论（audit items 1–4）+ **CSV 语义实证**（用 throwaway 探针确认，未对正式产物做任何改动）。
- 红线遵守：未碰板 / 未写 Flash / 未访问 test / 未启动 QAT / 未重训 / 未写任何 FINAL_* / NPU_PASS 等禁词。`model_24class_ZG` 保留为 REJECTED 证据，不晋升。

---

## 1. 能力审计（官方文档 + 二进制字符串确证）

| 项 | 结论 | 依据 |
|---|---|---|
| ZHUGE 每算子计算位宽 | **int8 / bf16 / fp16 / tf32**（`fp32`、`int16` 会报 `don't support dtype` 硬错） | `CalibratePass.dll` 字符串 + zhuge 文档 `qdtype=int8/bf16/fp16/tf32` |
| BUYI 每算子计算位宽 | int8 / int16 / fp32（int16 是 BUYI 专属，ZHUGE 无） | buyi 文档 `dtype仅支持INT8、INT16、FP32` |
| 每层 FP32 精度 | ZHUGE **不支持** CSV 置 fp32（报错）；仅 Input/Output 宿主算子 “only support fp32” | `don't support dtype = FLOAT32!` vs `only support fp32!` |
| 权重 per-channel | **默认已支持**（`per=channel`；ZC.json 末层 FC 权重 `@scales([axis=-2]24,…)`） | quantize log `Measuring Weight: channel N` |
| matmul_const per-channel | **暂不支持**（官方文档明示）；但本模型末层 FC 是普通 `Matmul`（非 matmul_const），权重已 per-channel | matmul 算子文档 |
| 混合精度 adapt/generate | 支持（CSV 在 quantize 阶段 `ConfigQDTypeByCSV` 应用，后续 adapt/generate 沿用） | 堆栈 `CalibratePass.cpp: ConfigQDTypeByCSV` |
| “对输出层使用更高的计算位宽” | 官方文档 **明确建议**；qdtype=int8 时 ZHUGE 高位宽默认 = **BF16** | zhuge/buyi 文档 3.4 节 Tips + autotune 段 |

**结论**：官方支持、且本任务可用的“输出层更高位宽”手段 = `mix_precision="xx.csv"` 将末层 FC（op 179）置 `bf16`，前端保持 `int8`。这是唯一官方语义，无需 QAT/重训/结构改动。

---

## 2. 节点名审计（分类头 / logits 节点）

| 层次 | 节点 | op_id / 名称 |
|---|---|---|
| ONNX (opset17) | ReduceMean | 节点 63 `/model/ReduceMean` |
| ONNX | FC1 Gemm | 节点 64 `/model/classifier/classifier.0/Gemm` |
| ONNX | ReLU | 节点 65 |
| ONNX | 末层 FC Gemm → `logits` | 节点 66 `/model/classifier/classifier.3/Gemm` |
| quantize 输入 `model_24class_optimized.json`（131 ops） | Mean | **op_id 176** (`icraft::xir::Mean`) |
| 同上 | FC1 Matmul | **op_id 177** (`icraft::xir::Matmul`) |
| 同上 | ReLU | op_id 178 |
| 同上 | 末层 FC Matmul → logits | **op_id 179** (`icraft::xir::Matmul`) |
| 同上 | Output | op_id 180 |
| 最终 NPU 候选 `model_24class_ZG.json`（130 ops） | Mean / FC1 / 末层 FC | op_id 1219 / 1151 / 1155 |

**CSV `op_type` 字符串（实证，见 §5）**：必须用 **RTTI 名带 `Node` 后缀**，即 `icraft::xir::MatmulNode` / `icraft::xir::MeanNode` / `icraft::xir::ReLUNode` 等（**不是** JSON 里的 `icraft::xir::Matmul`，也不是文档旧例里的 `conv`/`relu`）。

---

## 3. 量化 scale / 范围审计（Phase D 384 产物）

| 张量 | 值 |
|---|---|
| 末层 FC（op 179）输出 “logits” scale | **1.2439321**（24 维共享，sint8 对称，zero_point 空） |
| FC1（op 177）输出 scale | **0.12692387**（128 维共享，sint8 对称） |
| 末层 FC 权重 | per-channel `@scales([axis=-2]24 值,8*1)` |
| logits 饱和率 | **0.15%**（14/9216） |
| logits 值域 | **[−199.128, +38.717]**（严重不对称，偏负） |
| \|logit\| 分布 | 中位数 18.73，p99 120.1 |

**关键结论**：崩塌是**分辨率问题**（int8 步长 1.2439 对 AM-SSB-SC 与 AM-SSB-WC 近并列的小 logits 太粗），**不是饱和问题**（饱和率仅 0.15%）。

---

## 4. 逐层隔离审计（决定性发现）

`scripts/sensitive_layer_isolation_m29.py`（只读，不改任何模型文件）：用 vendor 精确 scale 逐层重量化 fp32 输出，对比 vendor 全 int8 logits（`work/eval_quant/quant_logits.npy`，1536 样本）。AM-SSB-SC（类 18）精度：

| 方案 | AM-SSB-SC acc | 相对 fp32 |
|---|---|---|
| fp32 | 51.6% | — |
| **仅输出层 int8**（scale 1.2439321） | **31.3%** | **−20.3pp（首要触发；精确复现 OOK=14 误判）** |
| 仅 FC1 输出 int8（scale 0.12692387） | 50.0% | −1.6pp（可忽略） |
| vendor 全 int8（前向激活+输出） | 7.8% | −43.8pp（崩塌） |

**结论**：**首要/最显著偏差 = 输出层（op 179）int8**；完整崩塌还需前端激活 int8 叠加。整改优先级：先修输出层（实验 A），前端暂保持 int8。

---

## 5. mix_precision CSV 语义实证（throwaway 探针，非实验 A）

探针目录 `F:\FPGA_Work\_tmp_m29_d1_csv_probe_20261010\`（2 张校准图，仅用于确认 CSV 格式；**不构成**实验 A）。

依次触发并确证：

1. 表头列名 = **`op_type`**（写 `type` 报 `[fatal] Can't find a column named op_type`）。
2. **必须列出全网络 131 个 op**（单行 CSV 报 `Mixprecision_config(op size = 1) Not Match Network(op size = 131)!`）。
3. `op_type` 值 = **RTTI 名带 `Node` 后缀**（写 `icraft::xir::Input` 报 `…opid:0, op type:icraft::xir::InputNode, but get icraft::xir::Input`）。
4. 采用 `op_type=icraft::xir::MatmulNode`、`dtype=bf16` 后**通过**：op 179 输出 `storage_dtype=@bf(16)`、`expressed_dtype=@fp(32)`、`scale=@scales([axis=-1])`（无 int8 逐维 scale）、`zero_points=[]`（对比 baseline `@sint(8)` scale 1.2439321）。
5. Input/Output 宿主算子（op 0/180）报 `only support fp32` 警告，维持 fp32，与 baseline 行为一致（无害）。

**正确 CSV 格式（v3.39.0）**：
```
op_id,op_type,dtype
0,icraft::xir::InputNode,int8
...
179,icraft::xir::MatmulNode,bf16
...
180,icraft::xir::OutputNode,int8
```
（131 行 = 全网络 op 数；`dtype` 取值 int8/bf16/fp16/tf32。）

---

## 6. 实验 A 设计（已定，待执行一次）

- **改动（单变量）**：`mix_precision` CSV 将末层 FC **op 179** 置 `bf16`；其余 130 op 全 `int8`（Input/Output 宿主节点仍 fp32）。前端网络保持 int8；分类头输出 24 维 logits 保持 fp32 语义。
- **不变**：无 softmax、无结构改动、无 QAT、无重训、标签序/预处理不变、同一 384 校准集（`work/calibration_384/`，seed 2028，24×16，26 SNR）+ 同一 1536 固定评测集（`work/eval_full/subset_index.npz`）。
- **流程**：quantize → adapt → generate → 评测（fp32 / ONNX / 真实量化 + AM-SSB-SC 混淆 + Top-1 一致率 + logits 边际分布 + 饱和率 + 产物 SHA），全新输出目录，只跑一次。
- **晋级门**：acc≤2pp、macro-F1≤2pp、rated≤2pp、snr0≤3pp、min_class≤5pp、无单类系统性崩塌、Top-1 一致率达标、无 NaN/Inf。

---

## 7. 待定 / 边界

- 实验 B（末层 FC/output per-channel）：官方文档“matmul_const 暂不支持按通道量化”，但本模型末层是普通 `Matmul`（权重已 per-channel 默认）。实验 B 仅当实验 A 后确认“官方支持末层 FC 输出按通道”才有意义，否则 B=A。
- `model_24class_ZG`（Phase D 全 int8）**保持 REJECTED 证据，不晋升、不上板**。
