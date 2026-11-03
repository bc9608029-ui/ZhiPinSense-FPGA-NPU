# M20 权威模型输出审计（`docs/M20_MODEL_OUTPUT_AUDIT.md`）

任务 M20 §二交付物。本文冻结**当前板端 12 类 NPU 模型**的完整身份与输出契约，
回答「NPU 到底输出什么」这一决定 OOD-U 评分方法可行性的根本问题。所有 SHA 均在本机
逐文件实测，证据代码位置均已给出文件+行号。

> 结论先行：**当前 NPU 输出是 12 维 raw fp32 logits（无 Softmax、无需主机反量化）。**
> 因此 MSP / Entropy / MaxLogit / Logit Margin / Energy **五种评分全部可用**，
> 无需从 softmax 概率伪造或反推 Energy。

---

## 0. 模型身份（与任务给定的 `model_sha` 一一对应）

| 项 | 值 |
|---|---|
| 模型标签 | **`12CLASS_CHAIN_VALIDATION_MODEL`** |
| **`model_sha`（任务给定）** | `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c` |
| 该 SHA 对应文件 | **`model_12class.raw`**（iCraft 编译产物·权值二进制，2,851,472 B） |
| 确认方式 | `model_12class.sha256` 边车 + 本地 `sha256sum` 复算一致 |

**完整溯源链（从训练 checkpoint → ONNX → NPU 编译产物，逐级 SHA 锁定）：**

| 层 | 文件 | 字节 | SHA256 |
|---|---|---|---|
| 训练 checkpoint（部署权值源） | `model_12class/seed2026_best.pt`（源 `formal/seed2026/checkpoints/best.pt`，epoch 22） | 3,504,977 | `7215290b0f43f8a8cc05f4ee135f2a9524cf8a8036b71ae52b0b6c94c02aae72` |
| 初始化 checkpoint | `public_pretrain/checkpoints/best.pt`（源 epoch 29，165 张量拷贝，排除 classifier 头） | — | `705a04790979ad7b2f8d419d9641161cee56e106116654d83a1f41405760e289` |
| 源 ONNX（fp32 部署模型） | `model_12class/ad_amr_v1_1_opset17.onnx` | 1,126,095 | `f77587152b52cda9a467b28790bc62d0eb0c639db2c39da82642c00ca8deda5a` |
| NPU 编译图 | `model_12class/model_12class.json` | 222,804 | `51364bdf49d280944094f7af89ea4c759b3ae4d0d350be5f8c43e0c5849ab834` |
| NPU 编译权值（**= model_sha**） | `model_12class/model_12class.raw` | 2,851,472 | `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c` |

> 冻结结论：任务给定的 `model_sha=2ae95275…` **已确认**为 `model_12class.raw`；
> 它不是 checkpoint、不是 ONNX，而是 iCraft 对 fp32 ONNX 做 int8 量化后的 NPU
> 权值二进制。上游 fp32 权值源 = `seed2026_best.pt`（`7215290b…`），二者经 ONNX
> `f7758715…` 一一对应。

---

## 1. 标签顺序（严格 12 类，已逐项核对）

| idx | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 类 | OOK | 4ASK | AM-DSB | WBFM | 2FSK | GFSK | BPSK | QPSK | 8PSK | 16QAM | 64QAM | OFDM |

- 与任务要求顺序**逐项一致**。
- 权威源（两处字节一致，SHA `cd3f336d…`）：`sdr_adapter/categories.hpp` `cat::target_12()`
  （`sdr_pluto_board_integration_v1` 与 `sdr_preparation_v3_logging_fix` 副本一致）。
- 训练侧权威：`acceptance.json.class_contract`（12 类，与上一致）。
- 板端程序只从 `cat::target_12()` 取序，不另写。

---

## 2. 输入契约

| 项 | 值 |
|---|---|
| 形状 | `[N, 2, 1024]`（单样本 `[1,2,1024]`） |
| 布局 | planar I/Q，C 序：先 1024 个 I，再 1024 个 Q |
| dtype | fp32（`@fp(32)`），单样本 8192 字节 |
| 归一化 | 训练域 RMS≈1.0（**不再归一化**，模型内部自算特征） |
| 输入量化 | **否**（`no_transinput=true`，输入保持 fp32） |

证据：`model_12class/MODEL_DEPLOYMENT_CONTRACT.md` §1/§4/§5；`npu_classifier.hpp:82-101`
（`kTensorFloats` 连续 FP32 `[1,2,1024]`）。

---

## 3. 输出格式（本审计核心结论）

### 3.1 结论：raw fp32 logits，`[1,12]`，48 字节

**不是** softmax 概率、**不是** int8/int16 量化 logits、**不需要**主机反量化。

### 3.2 证据（三重独立）

**(a) ONNX 算子白名单无 Softmax**：`ad_amr_v1_1_opset17.onnx` 仅含
`Add(12) / Conv(28) / Gemm(2) / ReduceMean(1) / Relu(24)`（opset 17 / IR 8）。
`export_report.json.inspection.op_types` 与 `unexpected_operators: []` 同证。
→ 模型输出是 logits 前的原始分数，无概率化。

**(b) NPU 编译图输出节点是纯 fp32（无量化类型）**：`model_12class.json` 末位 op
（`op_id 180`，`_type_key: icraft::xir::Output`，`compile_target: @hostt`）：

```json
"inputs": [{ "dtype": { "element_dtype": "@fp(32)",
                        "layout": "@layout(*C)",
                        "shape": [1, 12] },
             "mtype": "@chunk(42@0)" }]
```

输出 `element_dtype` 为**普通 `@fp(32)`**（非 `QuantizedType`，无 `scale`、无
`zero_point`），shape `[1,12]`，落在 `@hostt`（主机张量）。→ 运行时直接把反量化后
的 fp32 logits 交给主机。

**(c) 板端代码按 fp32 读 12 个 logits，无任何换算**：
`board_package/npu_classifier.hpp:159-169`（`read_logits`）：

```cpp
if (bytes.size() != kLogitsCount * sizeof(float))   // 12 * 4 = 48
    throw std::runtime_error("unexpected logits size; expected 12 x FP32");
std::vector<float> logits(kLogitsCount);
std::memcpy(logits.data(), bytes.data(), bytes.size());  // 直接 memcpy，无 dequant
```

### 3.3 明确排除项

| 假设 | 判定 |
|---|---|
| 只输出 softmax 概率 | **否**（无 Softmax 算子；`npu_classifier.hpp` 直接读 logits） |
| int8/int16 量化 logits 需主机反量化 | **否**（输出边界 `@tf(32)`，运行时自动反量化） |
| 需伪造/反推 Energy | **不需要**（raw logits 直接可得，Energy = `-T·logsumexp(logits/T)`） |

---

## 4. 量化参数（内部 int8，输出边界 fp32）

| 项 | 值 |
|---|---|
| 方案 | INT8（非 FP16） |
| 存储 dtype | 内部 `@sint(8)`（276 处）；输入/输出边界 `@tf(32)`（22 处） |
| 对称性 | 对称（`zero_point(s)` 全为 `[]`，无零点） |
| 粒度 | per-channel（`scale: @scales([axis=-1]…)`，按输出通道） |
| 饱和方式 | KLD（`saturation="kld"`） |
| 输入量化 | 否（`no_transinput=true`） |
| 输出反量化 | 运行时自动（fp32 logits） |
| 示例首层权值标度 | `@scales([axis=-1]1024*0.23273507)`（首 Conv 1024 输出通道 per-channel 标度 0.23273507） |

**板端含义**（`MODEL_DEPLOYMENT_CONTRACT.md` §5）：程序喂 fp32 `[1,2,1024]`
（8192 字节），读回 fp32 `[1,12]`（48 字节）；**无需任何 int8 换算**。

---

## 5. 证据代码位置汇总

| 事实 | 位置 |
|---|---|
| 部署契约全文 | `model_12class/MODEL_DEPLOYMENT_CONTRACT.md` |
| 源 ONNX + SHA | `model_12class/ad_amr_v1_1_opset17.onnx`（SHA `f7758715…`） |
| 训练 checkpoint + SHA | `model_12class/seed2026_best.pt`（SHA `7215290b…`） |
| NPU 图 + SHA | `model_12class/model_12class.json`（SHA `51364bdf…`） |
| NPU 权值（model_sha） | `model_12class/model_12class.raw`（SHA `2ae95275…`） |
| 标签权威源 | `sdr_adapter/categories.hpp` `cat::target_12()`（SHA `cd3f336d…`） |
| 板端读 logits 代码 | `board_package/npu_classifier.hpp:159-169`（`read_logits`） |
| 板端输出契约校验 | `board_package/npu_classifier.hpp:152-157`（`check_output_contract`，断言 `[1,12]`） |
| 输出节点量化证据 | `model_12class.json` op_id 180（`@fp(32)` / `@hostt` / shape `[1,12]`） |

---

## 6. 审计结论（对应任务最终报告第 1、2 问）

1. **当前 NPU 能否取得 raw logits？** → **能**。输出为 fp32 raw logits `[1,12]`，
   运行时已反量化，板端直接 memcpy 读 48 字节。
2. **当前模型 SHA 是否确认为 `2ae95275…`？** → **是**，为 `model_12class.raw`
   （iCraft int8 编译权值），上游 fp32 源 `seed2026_best.pt`（`7215290b…`）→ ONNX
   `f7758715…` → NPU `2ae95275…` 逐级 SHA 锁定。

**对 OOD-U 评分的影响**：五种评分（MSP / Entropy / MaxLogit / Logit Margin /
Energy）**全部可用**，无需降级到「仅 MSP/Entropy」，也无需标 Energy 不可用。

---

## 7. 红线

- 本模型仅作**通路验证**（源 `acceptance.json` OOD gate 为 NO_GO），**非**「最终鲁棒
  模型 / 最终准确率 PASS / OOD PASS」。任何报告不得把 `12CLASS_CHAIN_VALIDATION_MODEL`
  写成最终 PASS 模型。
- M20 不重训 12 类、不改 NPU 权重、不改 RTL/XDC/位流、不改标签序/输入预处理/UI 布局/
  分类门限；新候选 `t017/seed2028` 不得替换当前 `2ae95275…` 模型。
