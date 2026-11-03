# M29 RML23 — 真实外部 QPSK 三后端根因判责报告

**日期** 2026-10-11 · **绑定指令** 39e5 · **证据目录**
`C:\Users\shado\Downloads\rml23_analysis_20261011_225430`

---

## 0. 一句话结论（判责）

**VERDICT：`MODEL_DOMAIN_GENERALIZATION`（模型 / 真实域泛化问题）**

三后端（FP32 源模型 / iCraft Host 量化后端 / 板端 NPU）对同一份真实 QPSK 捕获的
**78/78 帧全部判为 QAM（0×QPSK）**。板端 NPU 与 vendor Host 量化后端输出**逐位一致**
（cos=1.0、max_abs=0.0），板端只是**忠实复现了模型本身对真实域 QPSK 的错误分类**。

**根因不在**：量化、编译、板端 NPU/runtime/input-buffer、rec-scale、RX gain、标签、带宽、
频偏、混叠、缩放。**根因在**：expA_bf16_head 模型（RadioML2018 合成域训练）对真实信号
QPSK 泛化失败，把它折叠进 16/64/128/256-QAM。

---

## 1. 判定规则 → 命中

| # | 规则 | 本轮实测 | 命中 |
|---|---|---|---|
| 1 | FP32/Host/NPU 全部 QAM | FP32=0×QPSK、Host=0×QPSK、NPU=0×QPSK（全部 QAM） | **✅ 命中** |
| 2 | FP32=QPSK、Host/NPU=QAM（量化/编译） | FP32 也不是 QPSK | 否 |
| 3 | FP32/Host=QPSK、NPU=QAM（板端 NPU） | Host/NPU 逐位一致，均为 QAM | 否 |
| 4 | 三方不稳定（逐层查身份） | 三后端高度一致（见 §2） | 否 |

---

## 2. 三后端证据

对 **78 帧** 完全相同的 `live_rx_tensor_*.f32`（8192 B，`[2,1024]` FP32，plane0=I/plane1=Q），
未经任何重归一化 / IQ 交换 / 重排序 / 滤波 / 重采样。

### 2.1 混淆直方图（merged-23 top1 / raw24 argmax，QAM 区 1:1 一致）

| backend | 16QAM | 64QAM | 128QAM | 256QAM | **QPSK** |
|---|---|---|---|---|---|
| board_npu (A)    | 25 | 19 | 6 | 28 | **0** |
| host_quantized (B) | 25 | 19 | 6 | 28 | **0** |
| fp32_onnx (C)    | 21 | 15 | 5 | 37 | **0** |

板端结果与指令所述一致：28×256QAM、25×16QAM、19×64QAM、6×128QAM、0×QPSK。

### 2.2 一致率（top1）

| 比较 | 一致 | 说明 |
|---|---|---|
| NPU vs Host | **78/78 (100%)** | 且 **raw24 逐位一致**（cos=1.0、max_abs=0.0） |
| NPU vs FP32 | 63/78 (80.8%) | 分歧**仅在 QAM 族内**（16/64/128/256 之间），**从无 QAM↔QPSK** |
| Host vs FP32 | 63/78 (80.8%) | 同上 |
| 三后端全一致 | 63/78 (80.8%) | — |

### 2.3 原始 logits 距离

| 对 | max_abs_error (min/med/max) | mean_abs_error (med) | cosine (min/med) |
|---|---|---|---|
| NPU vs Host | 0.0 / **0.0** / 0.0 | 0.0 | 1.000000 / 1.000000 |
| NPU vs FP32 | 3.11 / 8.01 / 16.91 | 3.10 | 0.995285 / 0.998979 |
| Host vs FP32 | 3.11 / 8.01 / 16.91 | 3.10 | 0.995285 / 0.998979 |

**判读**：
- NPU≡Host **逐位**：板端 NPU 精确执行编译后的 bf16 模型，**零板端/runtime/输入缓冲误差**。
- FP32 与量化后端 logits 差 ~8（logits 域在 −90…−7 量级），cosine>0.995：这是 **bf16 量化
  的正常扰动**，只引起 QAM 子类（16/64/128/256）边界跳变，**从不把 QAM 判回 QPSK**。

### 2.4 关键帧例（frame 10）

`raw24` 六类 logits（越小越不可能，argmax 为最大）：

| 后端 | BPSK(3) | **QPSK(4)** | 16QAM(12) | 64QAM(14) | 128QAM(15) | 256QAM(16) | top1 |
|---|---|---|---|---|---|---|---|
| board_npu | −42.5 | **−16.88** | −8.38 | **−7.66** | −16.62 | −11.88 | 64QAM |
| host_quantized | −42.5 | **−16.88** | −8.38 | **−7.66** | −16.62 | −11.88 | 64QAM |
| fp32_onnx | −44.43 | **−14.61** | −10.38 | **−6.95** | −12.94 | −11.77 | 64QAM |

三后端都把 QPSK（−16.88/−14.61）压在 16QAM（−8.38）、64QAM（−7.66）、256QAM（−11.88）
之下——模型本身就没给真实 QPSK 以 QPSK 判类，而非后端把它改坏。

---

## 3. 冻结身份（指令任务 7）

| 身份 | 值 |
|---|---|
| model JSON SHA256 (`model_24class_ZG.json`) | `d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d` |
| model RAW SHA256 (`model_24class_ZG.raw`) | `2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba` |
| `params_md5`（json 字段） | `7966a4829fc713b2e8ea6c04168be263` |
| FP32 源模型 `rml24_24class_opset17.onnx` SHA256 | `976618a131e75f23bd46e04e71a114cbbea245d6afdd4c7ea7fa008e0ce9ed51` |
| 板端 logits 声明的 `model_sha` | `2425d990…`（== 冻结 raw） |
| tensor | 78 帧，每帧 `input_sha256` 与 `live_rx_tensor_*.f32` 字节 SHA **全部一致**（0 mismatch） |

**后端版本**：
- A 板端 NPU：iCraft ZG330，编译 bf16 模型 `model_24class_ZG`（v3.39.0）。
- B Host 量化：iCraft **v3.39.0** HostBackend（`icraft-run --backends Host`，同一编译模型）。
- C FP32 参考：onnxruntime **1.30.0** CPU，opset17 源模型。

24 类标签序（冻结契约）：`0=OOK … 3=BPSK, 4=QPSK … 12=16QAM, 14=64QAM, 15=128QAM,
16=256QAM, 17=AM-SSB-WC, 18=AM-SSB-SC, … 23=OQPSK`。合并契约 `17/18 → 17`（logaddexp）。

---

## 4. 与独立 DSP 复核的关系（为什么“信号没问题、判类错”）

独立复核已证信号是正常中心窄带 QPSK（99.986% 功率在中心 ±16 kHz，90/95/99% OBW
15.1/16.5/18.6 kHz，中心偏移约 −250 Hz，complex RMS≈1.024、golden 标量 RMS≈0.707）。
本次 `analyze_live_rx_capture.py` 修复后复算：

| 指标 | 修复后（78 帧 median） | 独立复核 |
|---|---|---|
| 90% OBW | 119 bin = **14.9 kHz** | 15.1 kHz |
| 95% OBW | 131 bin = **16.4 kHz** | 16.5 kHz |
| 99% OBW | 151 bin = **18.9 kHz** | 18.6 kHz |

带宽/频偏/缩放**都正常**，与复核一致。信号域干净，问题**不在射频/前端/预处理**，而在
模型对真实 QPSK 的判类。

---

## 5. 本轮修复（脚本，非模型/数据）

1. **`scripts/compare_three_backends.py`**（指令任务 1，独立包导入错误）：
   - 原先 `sys.path.insert(_HERE/../../postprocess)` 在独立解包后失效（包内无
     `postprocess/rml23_merged.py`）。
   - 现改为按序解析并 `importlib` 加载**冻结** `rml23_merged.py`：`--merge-module` →
     包内 `../postprocess/` → 冻结工程 `../../postprocess`；**逐字节复用官方 merge**，
     未重写、未改逻辑。
   - 并把冻结 `postprocess/rml23_merged.py` 复制进包（`postprocess/rml23_merged.py`，
     SHA `0d4a9eaf…`，与冻结逐字节一致；`contracts/rml23_merged_contract.py` 包内本已存在）。
   - 新增 `--host-dir`（Host 量化 `logits_*.json` 目录），补齐 live-rx 三后端比较入口；
     输出逐帧 top1 + 混淆直方图 + 三后端一致率。

2. **`scripts/analyze_live_rx_capture.py`**（指令任务 8，OBW + power 修复）：
   - 根因：`np.fft.fft` 把 DC 放在 bin 0、负频在上半，中心窄带载波横跨数组回绕点，
     **非环形**“最小连续带”被迫横跨几乎整个数组 → 把干净 16 kBaud QPSK 误报成
     ~128 kHz 满带宽（1024 bin）。
   - 修复：**先 `fftshift`（DC 置中）再做最小连续带搜索**，回绕不再发生。
   - `power_dbfs` 误用于“已缩放模型张量”，改为 `rms`（线性）+ `power_db_re_unit`
     （相对单位 RMS 参考，**不再称 dBFS**）。
   - 新增合成 **16 kBaud、RRC β=0.35 QPSK 自检**；自检 **7/7**（含中心 CW 回绕用例）。

---

## 6. 红线遵守声明

本轮**未**修改模型、标签、golden、预处理、RTL、位流、Flash；**未**再调 rec-scale / RX gain /
标签 / 多数表决；**未**训练任何模型；**未**写任何 `*_PASS` / `PROJECT_COMPLETE` / `FINAL_*`；
**未碰板**。三后端与两脚本均为纯诊断/判责改动。

## 7. 产物

- `out/three_backend_judgment.json` — 78 帧逐帧三后端原始 logits + pairwise 距离 + 混淆 +
  一致率 + verdict（权威机读结果）。
- `out/fp32_logits/`、`out/host_logits/` — 78 帧 FP32 / Host 量化 24 维 logits（`logits_*.json`）。
- `run_three_backend_judgment.py` — 复现脚本（读板端 + 跑 FP32/Host + 出判责）。
