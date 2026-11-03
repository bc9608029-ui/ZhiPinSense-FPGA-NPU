# M20 Logits 一致性契约（`docs/M20_LOGITS_PARITY_CONTRACT.md`）

任务 M20 §十一交付物，回答最终报告第 5 问「阈值是否来自 NPU 真实输出」与第 10 问
的「代码 READY / 离线 READY / 硬件 READY」边界。本文冻结**主机 fp32 参考 logits
与板端 int8-NPU 实际 logits 的一致性判据**，是 `run_m20_npu_logits_capture.sh` →
`run_m20_logits_parity.sh` 的权威口径。

> 上游前提见 `docs/M20_MODEL_OUTPUT_AUDIT.md`：当前 NPU 输出为 **fp32 raw logits
> `[1,12]`（运行时已反量化）**，板端 `npu_classifier.hpp` 直接 memcpy 读 48 字节，
> 无需主机反量化。因此 NPU 实测 logits 可与主机 fp32 logits **直接数值比对**。

---

## 1. 三条 logits 来源

| 来源 | 载体 | 数值类型 | 作用 |
|---|---|---|---|
| **PyTorch fp32**（权威参考） | `model_12class/seed2026_best.pt`（SHA `7215290b…`）经 `ADAMRV11Net` 前向 | fp32 raw logits | 阈值冻结与盲测所用的参考 |
| **ONNX fp32**（部署中间态） | `model_12class/ad_amr_v1_1_opset17.onnx`（SHA `f7758715…`） | fp32 raw logits | 与 PyTorch 做两方 fp32 一致性 |
| **NPU int8**（板端真实） | `model_12class/model_12class.raw`（SHA `2ae95275…`）编译后运行 | fp32（内部 int8，输出边界已反量化） | 与 fp32 参考做三方一致性 |

三方形成一条 SHA 锁定链：checkpoint `7215290b…` → ONNX `f7758715…` → NPU
`2ae95275…`，逐级一一对应（见模型输出审计）。

---

## 2. 容差契约（`tools/compare_logits.py`）

| 判据 | 值 | 语义 |
|---|---|---|
| `FP32_MAX_ABS_DIFF` | `1e-4` | PyTorch vs ONNX 的紧容差（同 opset/同权重，仅算子实现差异） |
| `NPU_MAX_ABS_DIFF` | `0.60` | int8-NPU vs fp32 的松容差：覆盖输出边界一个量化步长 + 安全裕量 |
| argmax 一致 | 逐样本比对 `argmax` | 拒识/分类的**类别下标**必须一致 |

- **int8 量化步长**：模型输出边界 per-channel 标度约 `0.23273507`（`MODEL_OUTPUT_AUDIT.md`
  §4 首层权值标度示例；输出边界 `@fp(32)` 运行时反量化）。一个量化步长约 0.23，
  故 `NPU_MAX_ABS_DIFF = 0.60`（约 2.5 步 + 裕量）是**宽松但非任意**的判据，用于
  容忍 int8 量化误差，同时仍能捕获「NPU 输出完全错误 / 陈旧帧 / 布局错乱」这类
  结构性问题。
- `compare_logits` 返回 `max_abs_diff / mean_abs_diff / argmax_agreement / within_tolerance`
  （`tools/compare_logits.py:39-54`）；任一比对 `within_tolerance=False` 即
  `M20_RESULT result=FAIL`（`scripts/m20_logits_parity.py:78-93`）。
- **离线 int8 仿真**：`tests/test_m20_parity_onnx.py::test_npu_int8_replay_within_tolerance`
  用 `scale=0.23273507` 对 fp32 logits 做 `round(pt/scale)*scale` 模拟 int8 量化，
  再以 `NPU_MAX_ABS_DIFF=0.60` 校验，证明该容差在量化误差下仍成立。

---

## 3. 固定 parity 集（`scripts/m20_parity_data.py`）

**目的**：板端捕获工具与主机参考喂的是**完全相同的字节**，NPU 列才有可比性。

- **生成**（`build_parity_iq`，`_PARITY_SEED = OOD_SEED + 77 = 12677`）：
  - 已知 12 类 × {0, 10} dB = **24** 样本；
  - near_12 代表 {8ASK, 16PSK, 32QAM, OQPSK} @10 dB = **4** 样本；
  - far 代表 {LFM, CW, MULTITONE} @10 dB = **3** 样本；
  - 合计 **N = 31**，落盘为 raw fp32 planar `[31, 2, 1024]`（`parity_iq.bin`）。
- **落盘产物**（`save_reference_bundle`）：
  - `parity_iq.bin`（raw fp32，C 序 planar I/Q）+ `parity_iq_meta.json`（n/shape/dtype/
    layout/sample_length/labels/parity_seed/`iq_sha256`）；
  - `reference_pytorch_logits.json` / `reference_onnx_logits.json`（`{n, output_dim, logits}`）。
- 标签形如 `id:16QAM@10dB` / `ood:near_12:16PSK@10dB` / `ood:far:LFM@10dB`，仅供
  审计，不参与决策。

---

## 4. 板端捕获契约（`scripts/m20_npu_logits_capture.py` + `tools/capture_npu_logits.cpp`）

**离线只准备参考**，板端捕获由用户本人在 ZG330 执行（我禁碰板）。

- 板端工具 `tools/capture_npu_logits.cpp` 消费 `parity_iq.bin` + `parity_iq_meta.json`，
  逐帧 `[1,2,1024]` fp32 送 `npu_forward`（板端实现为已部署的 `NpuClassifier12`），
  写出**规范 schema** `npu_logits.json`：

  ```json
  { "n": 31, "output_dim": 12, "logits": [[12 floats], ...] }
  ```

  `logits[i]` 是 `parity_iq.bin` 第 i 帧的 12 维 raw fp32 logits（无 Softmax）。
- 工具双模式：`--mode=board`（真 NPU 前向，`npu_forward` 板端接线点）与
  `--mode=replay`（主机用预 dump 的 logits 回放，验证 I/O 契约而无需 NPU，
  `tools/capture_npu_logits.cpp:114-154`）。主机构建仅编译 I/O 路径，`npu_forward`
  在主机返回 -1（`capture_npu_logits.cpp:36-40`）。
- `run_m20_npu_logits_capture.sh` 产出 `capture_contract.json`，其中 `board_execution.then`
  明确指向下一步：`run_m20_logits_parity.sh --npu-logits npu_logits.json --manifest
  runs/m20_threshold_calibration/ood_u_threshold_manifest.json`。

---

## 5. 阈值是否来自 NPU 真实输出（第 5 问，诚实口径）

| 项 | 现状 |
|---|---|
| **离线已做** | 阈值 `logit_margin / id_accept_99 ≈ -0.153` 来自**权威 fp32 checkpoint 的 logits**（`ood_validation` 校准，`ood_u/calibrate.py`），并经 PyTorch↔ONNX 两方 fp32 parity（`1e-4`）+ int8 仿真（`0.60`）验证。 |
| **离线未做** | **未**在真实 NPU 上跑 `run_m20_npu_logits_capture.sh` 取得板端真实 logits——离线环境无 ZG330，实机由用户执行。 |
| **决策一致性桥** | 一旦板端 `npu_logits.json` 到位，`run_m20_logits_parity.sh --npu-logits … --manifest …` 会在**冻结阈值下**计算 `pytorch_vs_npu_decision_agreement`（`m20_logits_parity.py:73-76`），确认 int8-NPU 与 fp32 参考给出**相同的 known/UNKNOWN 决策**，阈值才对 NPU 生效。 |

**结论**：阈值当前是**代码 READY + 离线 READY**；它来自权威 fp32 logits（与 NPU
权值 `2ae95275…` 一一对应），并已通过 int8 仿真容差校验；**「来自 NPU 真实输出」的
最终确认需用户上板完成 §4 的捕获 + §5 的决策一致性比对**，在此之前不写
`OOD_U_PASS / HARDWARE_PASS`。

---

## 6. 红线

- 不重训 12 类、不改 NPU 权重、不改 RTL/XDC/位流、不改标签序/输入预处理。
- 若只有概率输出则**不得伪造/反推 Energy logits**（本审计已证当前模型是 raw
  logits，此条不触发，但仍作为 fail-closed 前提记录）。
- 板端捕获与上板测试由用户本人执行，我禁碰板/禁写 Flash；未实机验证只能写
  `READY-FOR-M20-12CLASS-OOD-U-HARDWARE-TEST`，绝不写 PASS。
