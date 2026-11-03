# 标签本体（Label Ontology）

本文档冻结 12 类与 24 类两套标签序之间的语义关系，用于 OOD（开集/未知类）评测时
把「名字不同但物理上相近」的调制从主指标中剔除，避免把本该算「未知」的类当成「已知」。

## 两套冻结标签序

| 集合 | 类数 | 标签 |
|---|---|---|
| 12 类（板端部署） | 12 | OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM |
| 24 类（RadioML2018.01A） | 24 | OOK, 4ASK, 8ASK, BPSK, QPSK, 8PSK, 16PSK, 32PSK, 16APSK, 32APSK, 64APSK, 128APSK, 16QAM, 32QAM, 64QAM, 128QAM, 256QAM, AM-SSB-WC, AM-SSB-SC, AM-DSB-WC, AM-DSB-SC, FM, GMSK, OQPSK |

## 精确同名（COMMON）

两套序中**完全同名**的类（7 个）：`OOK, 4ASK, BPSK, QPSK, 8PSK, 16QAM, 64QAM`。
这些类在跨模型比较时可直接对齐。

## 近义/歧义（AMBIGUOUS，不进主 OOD 指标）

| 12 类名 | 24 类名 | 说明 |
|---|---|---|
| WBFM | FM | 宽带 FM vs 窄带 FM |
| GFSK | GMSK | 高斯成形 FSK vs 高斯 MSK |
| 2FSK | GMSK | 二电平 FSK vs 高斯 MSK |
| AM-DSB | AM-DSB-WC | 通用 DSB vs 含载波 DSB |
| AM-DSB | AM-DSB-SC | 通用 DSB vs 抑制载波 DSB |

OOD 评测中，这些「近义」配对被标记为 **ambiguous**：既不计入 ID 已知正确，也不计入
OOD 未知正确，单独统计，避免高估或低估开集性能。

## OOD 数据方向

- **对 12 类模型而言的近 OOD**（在 24 类中、不在 12 类中）：8ASK, 16PSK, 32PSK,
  16APSK, 32APSK, 64APSK, 128APSK, 32QAM, 128QAM, 256QAM, AM-SSB-WC, AM-SSB-SC,
  AM-DSB-WC, AM-DSB-SC, FM, GMSK, OQPSK。
- **对 24 类模型而言的近 OOD**（在 12 类中、不在 24 类中）：2FSK, GFSK, OFDM
  （以及 AM-DSB、WBFM，但归入 ambiguous）。
- **远 OOD（两模型共用）**：LFM/chirp、CW、多音、脉冲、跳频片段、窄带/宽带干扰。

## 红线

- 标签顺序一经冻结绝不重排；改动必须同步 `contracts/rml24_contract.py`、
  `datasets/radioml2018_dataset.OFFICIAL_CLASS_ORDER`、`data/radioml2018/classes.txt`
  三处并重算 SHA。
- 主 OOD 指标**绝不**把 ambiguous 配对当作已知或未知正确来源。
