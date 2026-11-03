# RML24 训练方法审计（V1.1）

本文回答 24 类（RadioML2018.01A）训练管线的 **15 个方法学问题**，并给出逐条
**fail-closed 审计结论**（引用代码行）。目的是在正式 AutoDL 训练前冻结训练口径，
避免"看似训练成功、实则口径不一致"的隐性错误。

> 所有行号以 `sdr_amr_rml24_ood_v1_1` 当前源码为准。

## 一、15 问

### Q1. 模型输入是什么？

`[N, 2, 1024]` fp32 **planar I/Q**（`[real, imag]`），每样本已 RMS≈1.0，**不做任何
再归一化**。契约见 `contracts/rml24_contract.py:30`（`INPUT_SHAPE = (1, 2, 1024)`），
注释明确"RadioML 样本已按样本归一化到单位 RMS，与 12 类板端 RMS-1.0 契约一致"。
`RadioML2018Dataset.__getitem__` 把 HDF5 的 `[1024, 2]` 转成 planar `[2, 1024]`。

### Q2. 标签顺序是什么？

冻结 24 类序 `LABEL_ORDER_24`（`contracts/rml24_contract.py:15-20`）：

```
OOK, 4ASK, 8ASK, BPSK, QPSK, 8PSK, 16PSK, 32PSK,
16APSK, 32APSK, 64APSK, 128APSK, 16QAM, 32QAM, 64QAM,
128QAM, 256QAM, AM-SSB-WC, AM-SSB-SC, AM-DSB-WC,
AM-DSB-SC, FM, GMSK, OQPSK
```

该顺序与 `datasets.radioml2018_dataset.OFFICIAL_CLASS_ORDER` 逐项一致，训练、评估、
导出、OOD 全部使用同一元组，**禁止重排**。

### Q3. 参数量 / 输出维是多少？

复用 `ADAMRV11Net`，`num_classes=24`，输出 **24 个 raw logits**（无 Softmax）。
输出维契约 `OUTPUT_DIM = 24`、`OUTPUT_KIND = "raw_logits_no_softmax"`
（`contracts/rml24_contract.py:31-32`）。`models/rml24_net.py` 的 `RML24Classifier`
对 `forward` 只返回 logits，导出时由 `scripts/export_rml24_onnx.py:_assert_no_softmax`
强制"模型内不含 Softmax/LogSoftmax"。

### Q4. 损失数学是什么？

在 `v2/trainer.py:124-145`（`_classification_loss`）+ `v2/losses.py`，总损失为
`cls_loss + reconstruction_weight * mse(denoised, clean)`，其中 RadioML 无干净参考信号，
`reconstruction_weight=0.0`（`configs/rml24_base.yaml:43`），即 denoiser 分支只作特征
正则、不参与损失。分类项四种（`v2` 的 `loss` 轴）：

- **cross_entropy**：`F.cross_entropy(logits, labels, reduction="none")` 后按 SNR 权重
  `snr_weights`（`training/ad_amr_v1_1_loss.py:45-53`）加权平均
  （`< -10dB → 0.35`，`>= 0dB → 1.25`，`== 0dB → ×1.2`）。
- **focal**：`ce = CE(reduction=none)`，`prob = exp(-ce)`，`((1-prob)^gamma * ce).mean()`
  （`v2/losses.py:39-44`）。
- **label_smoothing**：`F.cross_entropy(..., label_smoothing=smoothing)`
  （`v2/losses.py:32-36`）。
- **class_balanced**：`F.cross_entropy(..., weight=class_weights)`
  （`v2/losses.py:47-51`），权重来自 `_build_class_weight`。

### Q5. class_weight 从哪来？

`v2/trainer.py:106-122`（`_build_class_weight`），由 `v2.class_sampling` 轴决定：

- 默认 `"balanced"` → 返回 `None`（**不做类别加权**，24 类按 (类别,SNR) 分层、每层 4096，
  本身均衡）。
- `"hard_example_16qam_64qam"` → 仅 16QAM/64QAM 置 `3.0`（可选消融轴，非默认）。

设备一致性（Task A）：`__init__` 里 `class_weight.to(device)`，`_classification_loss` 里
再防御性 `weight.to(device=logits.device, dtype=logits.dtype)`；`v2/losses.py:_as_logits`
对 focal/label_smoothing/class_balanced 的权重同样 `to(logits.device/dtype)`。

### Q6. 优化器是什么？

`adamw`（`AdamW`，lr/wd 见 config）或 `sgd`（`SGD` + `momentum=0.9`），由
`v2.optimizer` 轴决定（`v2/trainer.py:70-81`）。默认 `adamw`，`learning_rate=1e-3`、
`weight_decay=1e-4`（`configs/rml24_base.yaml:34-35`）。

### Q7. scheduler / 早停怎么配？

- scheduler：`ReduceLROnPlateau(mode="max", factor=0.5, patience=5, min_lr=1e-6)`
  （`v2/trainer.py:83-87`），监控选择指标，`factor` 衰减。
- 早停：`minimum_epochs_before_stopping=30`、`early_stopping_patience=12`、
  `min_delta=1e-4`（`v2/trainer.py:63-65`）；连续 `patience` 轮未提升即停
  （`v2/trainer.py:239-241`）。

### Q8. 用 AMP 吗？

用。`amp: true`、`amp_dtype: bfloat16`（`configs/rml24_base.yaml:44-45`）。
`v2/trainer.py:89-98`：CUDA 下 `torch.autocast(dtype=bf16)`；`GradScaler` 仅在 FP16 路径
启用（bf16 指数域与 FP32 相当，无需缩放）。CPU/离线环境自动关 AMP（`device.type == "cuda"` 判定）。

### Q9. 有梯度裁剪吗？

有。`gradient_clip_norm=2.0`（`configs/rml24_base.yaml:42`），在 `scaler.unscale_` 之后
`clip_grad_norm_(params, 2.0)`（`v2/trainer.py:176-178`）。

### Q10. checkpoint 选择指标是什么？

**单一真相 = validation `rated_0_20_accuracy`**（SNR ∈ [0,20] 的准确率）。
`v2/trainer.py:200-204`：`score = val_metrics["rated_0_20_accuracy"]`，`best.pt` 只在该
指标 `> best + min_delta` 时保存（`v2/trainer.py:224-229`）。原加权 blend
`selection_score` 仍写入 history 报告，但**不再参与 checkpoint 选择**；pilot 排名
（`training/rml24_pilot.py`）、候选选择（`rml24_select`）、formal 最优种子
（`rml24_formal.py:132-141`）全部用同一指标。

### Q11. Pilot / Formal 预算是多少？

冻结于 `configs/search_space_rml24.yaml`：

- **pilot**：`n_pilot_trials=12`、`pilot_epochs=20`、`pilot_seed=2026`
  （Optuna TPE，采样轴见下），去重后 `top_candidates=1`、`selection_metric_below=0.55`。
- **formal**：默认 **1 候选 × 3 种子 × 80 epoch**（`formal_epochs=80`）。
- 采样轴（离散，无增广/课程轴）：`losses × optimizers × lr × wd × focal_gamma ×
  label_smoothing`（`search_space_rml24.yaml:19-25`）。

### Q12. formal 种子数是几个？

`formal_seeds = [2026, 2027, 2028]`（`configs/search_space_rml24.yaml:11`），
`pilot_seed` 仍为 `2026`。每个 (候选,种子) 训练**恰一次**，`mean/std/worst-seed`
三值报告（`rml24_formal.py:107-126`）。

### Q13. test 集何时第一次被访问？

**仅在最终评估访问一次**。训练/选择/formal/阈值校准只用 train/validation；
`evaluate_rml24(..., split="test")` 由最终评估调用，并在结果里写
`final_blind_test_accessed: True`（`evaluation/evaluate_rml24.py:96`）。OOD 最终评分用
独立的 `ood_final_test` split，与 ID test 同样只评一次。

### Q14. fake-INT8 是怎么仿真的？

`symmetric int8 weights / fp32 activations`：逐参数取 `abs().max()` 为 scale，
`round(clamp(w/scale, -127, 127)) * scale`（`evaluation/evaluate_rml24.py:_apply_fake_int8`）。
只量化**权重**，激活保持 fp32；报告 FP32 vs fake-INT8 的准确率下降、per-class recall、
全混淆矩阵与近 QAM/PSK 混淆块（`fake_int8_report_rml24`，Task K 扩展）。

### Q15. 为什么 ADAMRV11Net 适配 RadioML2018.01A？

复用 12 类板端 `ADAMRV11Net`（CNN 特征提取 + 分类头），仅把 `num_classes` 设为 24
（`build_rml24_model(num_classes=24, **config["model"])`）。网络对 `[N,2,1024]` planar I/Q
做时频特征学习，输出 raw logits（Energy 分数的前提）；RadioML 无干净参考信号，故
denoiser 分支只作正则（`reconstruction_weight=0.0`）。网络结构本身不改，避免与 12 类
板端部署网络分叉。

## 二、逐条审计结论（fail-closed）

| # | 结论 | 依据 |
|---|---|---|
| 1 | train/val 预处理一致 | `RadioML2018Dataset` 同一类、同一 `__getitem__` 只按 `split` 选索引，无 train 专属增广（`rml24_base.yaml:80` `apply_channel_augmentation: false`） |
| 2 | val/test 无随机增广 | `build_rml24_loader` shuffle 仅 `split=="train"`；`evaluate_rml24` 用 `shuffle=False` |
| 3 | 无双重 softmax | 模型输出 raw logits，`_assert_no_softmax` 在导出时强制无 Softmax/LogSoftmax |
| 4 | CE 无预 softmax | 各损失均直接 `F.cross_entropy(logits, ...)`（`F.cross_entropy` 内部自带 log_softmax，不重复） |
| 5 | label ∈ [0, 23] | `classification_metrics(targets, predictions, num_classes=24)`；`RadioML2018Dataset` 按冻结 24 类索引回标签 |
| 6 | batch 无 NaN/Inf | `_run_epoch` 逐 batch `isfinite(loss)` fail-closed（`v2/trainer.py:169-173`）；`evaluate_rml24` 逐 batch `isfinite(out)` fail-closed |
| 7 | scheduler 实际生效 | `scheduler.step(score)` 每 epoch 调用（`v2/trainer.py:232`），`mode="max"` 与选择指标方向一致 |
| 8 | 早停存 best 非 last | `best.pt` 仅在选择指标提升时保存（`v2/trainer.py:224-229`）；`last.pt` 另存但下游（manifest/导出/OOD）只读 `best.pt` |
| 9 | 选择指标训练前冻结 | `rated_0_20_accuracy` 在 pilot/select/formal/trainer 四处一致，训练中不改 |
| 10 | 阈值/标签序/指标三者冻结 | 阈值锁 `far` 族 `ood_validation`（见 OOD 协议审计），标签序 `LABEL_ORDER_24`，指标 `rated_0_20_accuracy` 均不变 |

## 三、红线

- 64QAM 是已知模型问题（int8 量化精度），**不属本任务**，不得靠降门限"伪修复"。
- 训练不访问 test；test 只在最终评估访问一次。
- 离线环境**不执行正式 GPU 训练**；本审计只在离线包内静态成立，AutoDL 由 CUDA preflight
  与正式训练实际验证。
