# M24-A 24 类 TODO（等待正式模型训练）

> 状态：`24CLASS_MODEL_NOT_READY`
> 本文记录：真实 24 类模型接入前必须完成/确认的事项。当前 `m24_class24_stub.hpp`
> 只提供确定性假 logits（`simulated=true`），**不得**用于任何真实分类或门禁判定。

## 1. 冻结契约（本轮已固化，训练完成后直接复用）

```cpp
// m24_class24_contract.hpp
CLASS24_NUM_CLASSES   = 24
CLASS24_INPUT_CHANNELS = 2
CLASS24_INPUT_LEN      = 1024
CLASS24_INPUT_STRIDE   = 2048      // [N,2,1024] 每帧 2048 个 float（I/Q 交错）
```

标签序（权威 RadioML2018.01A，冻结自 `sdr_amr_rml24_ood_v1/data/radioml2018/classes.txt`）：

```
OOK, 4ASK, 8ASK, BPSK, QPSK, 8PSK, 16PSK, 32PSK, 16APSK, 32APSK,
64APSK, 128APSK, 16QAM, 32QAM, 64QAM, 128QAM, 256QAM, AM-SSB-WC, AM-SSB-SC,
AM-DSB-WC, AM-DSB-SC, FM, GMSK, OQPSK
```

## 2. 训练完成后要做的事

1. **产出正式 24 类 checkpoint**（`raw logits` 输出，无 Softmax），并生成其 SHA256。
2. **校验输入契约**：正式模型输入 `[N,2,1024]`、输出恰 24 维、标签序与本契约三方一致。
3. **替换 stub**：新增一个 `m24_class24_backend`（真实加载器，读 checkpoint SHA、
   `load_state_dict(strict=True)`、`class_names` 逐项核对、`out_dim==24`）；保留
   `m24_class24_stub.hpp` 仅用于离线/主机测试。
4. **结果字段对齐**：真实后端结果沿用 `Class24Result` 结构，但 `simulated=false`、
   并写真实 `model_id`（checkpoint SHA）；任何 `simulated==true` 的结果绝不进入门禁。
5. **OOD 接线**：24 类语义 OOD / 近 24 / 近 12 / 远 / ambiguous 的分数口径沿用
   `sdr_amr_rml24_ood_v1` 的 Energy/MSP 定义，**不共享** 12 类 OOD-U 阈值。
6. **上板前门禁**：只有真实 NPU logits 对齐后，才允许写任何 `*_PASS` / `FINAL_*`。

## 3. 明确禁止（红线，直到训练完成）

- 禁止用 pilot checkpoint / V2 12 类 checkpoint 冒充最终 24 类模型。
- 禁止伪造 NPU 模型、伪造 logits、报告假 logits 准确率。
- 禁止把 stub 的 `argmax`/`class_name` 当作真实分类写入门禁或事件报告为真实结果
  （事件里必须保留 `classify_status=UNKNOWN_EXPERIMENTAL` 或明确 `SIMULATED`）。
- 禁止写 `24CLASS_PASS` / `FINAL_MODEL_PASS` / `OOD_PASS` / `DEPLOYMENT_PASS`。

## 4. 最短接入路径（训练完成、checkpoint 到位后）

```
训练完成 → 产出 checkpoint + SHA
        → 写 m24_class24_backend（真实加载器 + 契约校验）
        → 主机 parity（PyTorch↔ONNX/INT8）
        → 事件/巡检 classify 回调切换为真实后端（simulated=false）
        → 上板 NPU logits 对齐
        → 才允许写最终门禁 PASS
```
