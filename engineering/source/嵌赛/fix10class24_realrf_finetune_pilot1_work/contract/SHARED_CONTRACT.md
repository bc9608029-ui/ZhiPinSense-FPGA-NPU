# M29-RML24-REALRF-FINETUNE-PILOT1 — 共享合同

状态：`…-SHARED-CONTRACT-FROZEN`（主线程冻结，三条并行线只读引用）

本文件与 `shared_contract.py` 同源冻结；`shared_contract.py` 是代码侧权威常量源。
任何 fork 不得修改合同；如需变更由主线程统一修订重广播。

## 1. 身份与红线

- 任务 token：`M29-RML24-REALRF-FINETUNE-PILOT1`（离线准备阶段）
- 24 类顺序：`OOK,4ASK,8ASK,BPSK,QPSK,8PSK,16PSK,32PSK,16APSK,32APSK,64APSK,128APSK,
  16QAM,32QAM,64QAM,128QAM,256QAM,AM-SSB-WC,AM-SSB-SC,AM-DSB-WC,AM-DSB-SC,FM,GMSK,OQPSK`
- 模型输入：`[2,1024]` f32 LE（行0=实部、行1=虚部），8192 字节。
- 冻结模型 SHA：JSON `28272abc…`、RAW `c1781aec…`、CKPT `96cd25f8…`（网络
  `model_24class`，架构 `ADAMRV11Net`）。**NPU JSON/RAW 不是训练 checkpoint**，不得
  反推权重；训练须从原始 PyTorch checkpoint 初始化。
- 原始 RadioML：`F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5`，SHA
  `e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38`（原生 200 kHz、
  sps=8、128 符号）。

## 2. RF 传输与公共协议（冻结）

- 2.56 Msps、2.4 GHz、18 MHz TX/RX 带宽、RX 35 dB、TX 衰减 ≤ -40 dB、残差门 0.100、
  至多 3 次重捕。
- burst 布局（复样本）：前导 1024(ZC) + guard 2048 + 训练 1024(16QAM) + 载荷 53760 +
  尾 1024(ZC) = 59904。载荷 = 1024 波形 cyclic_tile（52×1024+512），模型窗 = 载荷前
  1024 复样本。
- v2 幅度合同：SEED_BASE=3000000，source_id `fix1v2-waveform-corrected-24waveforms`，
  conversion `v2`。**原始 RadioML 主臂与 v2 物理修正波形分开**；本任务主指标只用原始
  RadioML 实例。

## 3. 会话 / 划分（冻结）

| 会话 | 角色 | 每类样本 | 总量 |
|---|---|---|---|
| S1 | Train | 10 | 240 |
| S2 | Train | 10 | 240 |
| S3 | Validation | 10 | 240 |
| S4 | Sealed Test | 10 | 240 |

- **固定分母 = 960**：缺失/门拒/非有限/无同步/削顶/hard-invalid 均不得从端到端分母剔除。
- **S4 封存**：模型与超参数确定前不得参与训练/早停/选模。
- 命名：`source_id = s{sn}_c{ci:02d}_i{inst:02d}`（sn∈1..4，ci∈0..23，inst∈0..9）。
- 四轮之间 dataset_index / source_id / source_iq_sha256 / TX payload SHA **零重叠**。

## 4. 数字基线口径

对 960 个源 IQ 逐样本跑冻结 Host BF16（强制分类，无门）。保存 label / digital_pred /
logits / model_input_sha256 / label_correct。数字基线错误**不得删除**。后续分别统计
same_error / new_rf_flip / board_fix / RF-数字一致率。

## 5. 门拒 / 失败样本处理

每个样本**无条件先保存**（raw RX CI16、恢复 1024 IQ、tensor.bin、24 维 logits、双预测、
capture_ok/no_sync/rx_clipped/hard_invalid、gate_pass/failure_token、CFO/定时/相关度/
残差/恢复参数、文件 SHA）。**保存动作在门控判断之前**。门拒若能形成有限 tensor 可
forced diagnostic 分类，必须标记诊断旁路，不得伪装生产结果。hard-invalid 或无 tensor
仍计入 960 分母。

## 6. 结果 TSV 字段（冻结，采集链/判读器共享）

```
session_id  source_id  class_index  class_name  dataset_index  split
source_iq_sha256  tx_payload_sha256  raw_rx_sha256  model_input_sha256  logits_sha256
digital_pred  digital_label_correct  board_pred1  board_pred2  label
capture_ok  no_sync  rx_clipped  hard_invalid  gate_pass  failure_token
coarse_cfo_hz  fractional_timing  timing_offset  corr  training_residual
training_residual_rel  a_real  a_imag  b_real  b_imag
```

## 7. 接收端可访问性（采集链红线）

接收端只允许用：公共同步段、公共训练段、固定公开帧结构、接收信号本身。**不得**读类别、
原始载荷 IQ、manifest 真尺度、私有窗口起点、oracle 恢复参数。Ethernet 只用于整轮
启动/停止、状态、文件传输，**不得**传逐样本恢复真值。

## 8. 微调实验（采集前只构建 + 自测，不正式训练）

- E0 冻结原模型不训练；E1 冻结特征提取器只训分类头；E2 解冻最后一个特征块+分类头；
  E3 全模型小学习率微调。
- 从原始可训练 checkpoint 初始化；每 batch 混合真实 RF 与原始 RadioML 数字样本（建议
  1:1）；交叉熵 + AdamW + 小范围学习率搜索 + 早停；超参数只据 S3 选，禁看 S4；至少 3
  个随机种子；保存每个实验配置/checkpoint/训练曲线/完整 SHA。Host 候选通过前不得转 NPU
  或上板。

## 9. 最终只允许的判决

`FINETUNE_PROMISING` / `FINETUNE_MARGINAL` / `FINETUNE_NO_GENERALIZATION` /
`DATA_PIPELINE_INVALID` / `BLOCKED_NO_TRAINABLE_CHECKPOINT` / `READY_FOR_BOARD_CAPTURE`。
禁止 RF_PASS / PROJECT_COMPLETE / FINETUNE_SUCCESS。

## 10. 并行纪律

A/B/C 各用独立子目录；共享 schema 以本文件为准，fork 不得各自设计不同字段；A 只负责
源数据+训练资产、B 只负责 TX/RX+落盘、C 只负责基线+判读+训练框架；gate9_phase.hpp、
主分发 CPP、公共协议文件由主线程统一合并；最终只发一个集成 PATCH。
