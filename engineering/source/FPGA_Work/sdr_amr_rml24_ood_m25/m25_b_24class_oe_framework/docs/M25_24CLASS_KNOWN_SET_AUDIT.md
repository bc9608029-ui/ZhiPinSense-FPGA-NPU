# M25-B 24 类已知集合审计（Known-Set Audit）

状态：**`24CLASS_BASELINE_NOT_FROZEN` / `24CLASS_OE_MODEL_NOT_TRAINED`**。
本文档只审计"已知集合"（标签序、输入契约、baseline/ONNX/NPU 占位、语义重叠），
不进行任何训练，也不制造任何可上板验收的结论。

## 1. 24 类标签序的权威来源

冻结 24 类标签序（`contracts/m25b_24class_contract.py::LABEL_ORDER_24`）：

```
OOK, 4ASK, 8ASK, BPSK, QPSK, 8PSK, 16PSK, 32PSK,
16APSK, 32APSK, 64APSK, 128APSK, 16QAM, 32QAM, 64QAM,
128QAM, 256QAM, AM-SSB-WC, AM-SSB-SC, AM-DSB-WC,
AM-DSB-SC, FM, GMSK, OQPSK
```

来源：`sdr_amr_rml24_ood_v1_1` 冻结常量（只读抄入，本框架运行时不 import 该工程）。
12 类序仅作 12↔24 本体参照（`LABEL_ORDER_12`）。

## 2. 标签文件与数据集 SHA（只读真值）

| 对象 | SHA256（64-hex） |
|---|---|
| 标签文件 `classes.txt` | `0814d7b5a522abacd1eb3052f89fb83a8e91f83cf53745e5a6b804dd1b85e3c8` |
| 数据集 HDF5 | `e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38` |
| 数据集 index | `9a035841baef299ac918ae64294d59ba2298c5f20852862d3dd4069547330335` |
| 12 类正式模型 raw（参考，禁覆盖） | `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c` |

以上 SHA 在 `contracts/m25b_24class_contract.py` 中被测试断言为 64-hex 且不可变。

## 3. 输入契约

- 形状 `[1, 2, 1024]`，平面 I/Q，每样本单位 RMS（≈1），**不做重缩放**。
- 输出 24 维 **raw logits（无 softmax）**。
- **无 stride-2048**：本契约里不存在该值（勿沿用 M24 C++ 契约的 stride 措辞）。

## 4. 占位（均未冻结）

| 对象 | 状态 |
|---|---|
| 24 类正式 baseline checkpoint | 占位，`24CLASS_BASELINE_NOT_FROZEN` |
| ONNX 导出 | 占位 |
| NPU 真实 logits 采集 | 占位（`npu_boundary` 报告 `NPU_LOGITS_MISSING`） |
| OOD 阈值 manifest | 占位，仅在 ood_validation 锁，写一次 |

## 5. 语义重叠（OOD 边界风险）

12 类与 24 类之间的语义重叠族，是近 OOD 拒绝与 Energy 阈值的主要难点：

| 12 类 | 24 类 | 关系 |
|---|---|---|
| `AM-DSB` | `AM-DSB-WC` / `AM-DSB-SC` | 同族，WC/SC 细分 |
| `WBFM` | `FM` | 同为 FM 族 |
| `GFSK` | `GMSK` | 同为高斯成形 FSK |
| `2FSK` | `GMSK` | FSK 族 |
| `OFDM` | （无） | 24 类无对应 → 近 OOD |

本框架的近 OOD 族 = `2FSK / GFSK / OFDM`，模糊族 = `AM-DSB / WBFM`
（从主 OOD 指标中排除，避免把"语义等价"当"离群"惩罚）。

## 6. 红线

- 24 类正式 baseline 冻结前禁止启动 OE 训练（`training/m25b_baseline_gate.py`
  在缺失时打印 `24CLASS_BASELINE_NOT_FROZEN` 并在训练前退出）。
- 不覆盖 12 类正式模型、24 类 pilot 及 checkpoint、M22/M23/M24 交付物、RTL/XDC/位流、
  FPGA 数据通路、当前标签序与输入预处理、历史工程与历史包。
- 不写任何 FINAL_* / *_PASS / *_COMPLETE / *_DEPLOYMENT 状态。
