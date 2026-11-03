#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shared_contract.py -- M29-RML24-REALRF-FINETUNE-PILOT1 共享合同（主线程冻结）。

这是三条并行线（A 源数据/训练资产、B 采集链、C 判读/基线/训练框架）唯一共享的
权威常量源。任何 fork **不得**修改本文件；如需变更，须主线程统一修订并重新广播。

本任务离线准备阶段：不上板、不发射、不训练（板端采集前）。红线继承项目全局红线。
"""
from __future__ import annotations

TASK = "M29-RML24-REALRF-FINETUNE-PILOT1"
TOKEN = "M29-RML24-REALRF-FINETUNE-PILOT1"
DATE = "2026-10-21"

# ---- 24 类类别顺序（冻结，权威 = radioml_clean_contract.LABEL_ORDER_24）----
LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
)
N_CLASSES = 24
CLASS_INDEX = {name: i for i, name in enumerate(LABEL_ORDER_24)}

# ---- 模型输入契约（冻结）---------------------------------------------------
MODEL_SAMPLES = 1024
MODEL_INPUT_LAYOUT = "[2,1024] f32 LE（行0=实部 I，行1=虚部 Q）"
MODEL_INPUT_BYTES = 8192

# ---- 冻结模型身份（不得反推权重，不得把 NPU JSON/RAW 当训练 checkpoint）----
FROZEN_MODEL_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
FROZEN_CKPT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"
MODEL_NETWORK = "model_24class"
MODEL_ARCH = "ADAMRV11Net"
MODEL_JSON_PATH = (r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work"
                   r"\sdr_rml24_fix10class24_original_radioml_npu_ab1"
                   r"\model_rml24_bf16\rml24_adamrv11_bf16.json")
MODEL_RAW_PATH = (r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work"
                  r"\sdr_rml24_fix10class24_original_radioml_npu_ab1"
                  r"\model_rml24_bf16\rml24_adamrv11_bf16.raw")

# ---- 原始 RadioML 数据源（冻结）--------------------------------------------
HDF5_PATH = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"
HDF5_SHA256 = "e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38"
RADIOML_NATIVE_FS = 200000.0          # 200 kHz 原生（数字域）
RADIOML_SPS = 8
RADIOML_N_SYMBOLS = 128

# ---- RF 传输契约（权威 = radioml_dualsdr_common）----------------------------
RF_FS = 2560000
RF_CENTER_HZ = 2400000000
RF_TX_BW = 18000000
RF_RX_BW = 18000000
RF_RX_GAIN_DB = 35.0
RF_TX_ATTEN_DB_MAX = -40.0
RF_RESIDUAL_GATE = 0.100
RF_MAX_RECAPTURE = 3

# ---- 固定公开幅度合同 S（评审 39e5 Blocker 1；权威 = radioml_dualsdr_common）--
# TX 数字缩放是统一公开常数 S，不是逐样本 native_rms/tx_scale：.i16 = quantize_ci16(
# cyclic_tile_1024_to_payload(iq), S)，S = 1600 / max|IQ|（960 源）。板端以
# payload_tx_scale=S、payload_tx_target_rms=0 撤销该公开数字缩放恢复 native 尺度，
# RF 真增益仍由固定幅度训练块估计、绝不经 manifest 读取（即「manifest 真尺度」红线）。
TX_MAX_COMPLEX_MAGNITUDE = 23.371109008789062   # max|IQ| over the 960 pilot1 sources
TX_DIGITAL_SCALE = 68.46059377833956            # 1600 / TX_MAX_COMPLEX_MAGNITUDE
TX_TARGET_RMS = 0.0                             # 0 = 无再缩放（.i16 已按 S 量化）

# ---- 公共协议 burst 布局（权威 = radioml_independent_rx_contract）----------
BURST_PREAMBLE_COMPLEX = 1024          # ZC 前导
BURST_GUARD_COMPLEX = 2048             # settling-zero
BURST_TRAIN_COMPLEX = 1024             # 16QAM 载荷训练块（增益/IQ 参考）
BURST_PAYLOAD_COMPLEX = 53760          # 载荷 = 1024 波形 cyclic_tile
BURST_TAIL_COMPLEX = 1024              # ZC 尾
BURST_TOTAL_COMPLEX = 59904
BURST_PAYLOAD_START = 3072

# ---- v2 幅度合同（权威 = radioml_v2_contract）------------------------------
SEED_BASE = 3000000
V2_SOURCE_ID = "fix1v2-waveform-corrected-24waveforms"
V2_CONVERSION_VERSION = "v2"

# ---- 会话 / 划分（冻结）----------------------------------------------------
# S1,S2=Train; S3=Validation; S4=Sealed Test（模型与超参数确定前不得参与训练/早停/选模）
SESSIONS = {
    "S1": {"role": "train",       "n_per_class": 10, "n_total": 240},
    "S2": {"role": "train",       "n_per_class": 10, "n_total": 240},
    "S3": {"role": "validation",  "n_per_class": 10, "n_total": 240},
    "S4": {"role": "sealed_test", "n_per_class": 10, "n_total": 240},
}
SESSION_ROLES = {k: v["role"] for k, v in SESSIONS.items()}
N_SESSIONS = 4
N_PER_CLASS = 10
N_TOTAL = 960                          # 固定分母（不剔任何帧）

# ---- 命名规则（冻结）-------------------------------------------------------
# source_id = f"s{sn}_c{ci:02d}_i{inst:02d}"，sn∈{1..4}，ci∈{0..23}，inst∈{0..9}
# 跨会话 dataset_index / source_id / source_iq_sha256 / TX payload SHA 零重叠。
def source_id(session_no: int, class_index: int, instance: int) -> str:
    return "s%d_c%02d_i%02d" % (session_no, class_index, instance)

# ---- 数字基线口径（冻结）---------------------------------------------------
# 对 960 个源 IQ 逐样本跑冻结 Host BF16（icraft-run --backends Host），强制分类（无门）。
# 保存 label / digital_pred / logits / model_input_sha256 / label_correct。
# 数字基线错误不得删除；后续分别统计 same_error / new_rf_flip / board_fix / 数字一致率。
DIGITAL_BASELINE_MODE = "host_bf16_forced_classify"

# ---- 门拒 / 失败样本处理（冻结）--------------------------------------------
# 每个样本无条件先保存（raw RX / 恢复 1024 IQ / tensor.bin / logits / 双预测 /
# capture_ok·no_sync·rx_clipped·hard_invalid / gate_pass·failure_token / 恢复参数 / SHA）。
# 保存动作在门控判断之前。门拒若能形成有限 tensor 可 forced diagnostic 分类，必须标记
# 诊断旁路，不得伪装生产结果。hard-invalid 或无 tensor 仍计入 960 分母。

# ---- 结果 TSV 字段（采集链/判读器共享 schema，冻结）-------------------------
RESULT_TSV_FIELDS = [
    "session_id", "source_id", "class_index", "class_name", "dataset_index",
    "split",                        # train / validation / sealed_test
    "source_iq_sha256", "tx_payload_sha256", "raw_rx_sha256",
    "model_input_sha256", "logits_sha256",
    "digital_pred", "digital_label_correct",
    "board_pred1", "board_pred2", "label",
    "capture_ok", "no_sync", "rx_clipped", "hard_invalid",
    "gate_pass", "failure_token",
    "coarse_cfo_hz", "fractional_timing", "timing_offset",
    "corr", "training_residual", "training_residual_rel",
    "a_real", "a_imag", "b_real", "b_imag",
]

# ---- 微调实验（冻结：E0-E3；只构建与自测，采集前不正式训练）-----------------
FINETUNE_EXPERIMENTS = ["E0", "E1", "E2", "E3"]
# E0 冻结原模型不训练；E1 冻结特征提取器只训分类头；E2 解冻最后一个特征块+分类头；
# E3 全模型小学习率微调。从原始可训练 checkpoint 初始化，不从 NPU RAW 反推权重。

# ---- 红线（继承项目全局红线 + 本任务新增）----------------------------------
RED_LINES = [
    "不训练（板端采集完成前）；不碰板/不操作 SDR/不发射（离线准备阶段）",
    "不改生产恢复/门/协议；冻结模型 SHA 不变；不从 NPU RAW 反推权重",
    "960 分母固定，不剔门拒/失败/hard-invalid 样本",
    "接收端不得读取类别/原始载荷 IQ/manifest 真尺度/私有窗口起点/oracle 恢复参数",
    "Ethernet 只传整轮启动/停止/状态/文件，不传逐样本恢复真值",
    "S4 在模型与超参数确定前不得参与训练/早停/选模",
    "原始 RadioML 主臂与 v2 物理修正波形分开；主指标只用原始 RadioML 实例",
    "四轮 source_id/dataset_index/source_iq_sha256/TX payload SHA 零重叠",
    "不得写 RF_PASS / PROJECT_COMPLETE / FINETUNE_SUCCESS",
]

# ---- 权威合同源文件（只读引用，fork 不得改）---------------------------------
AUTHORITATIVE_FILES = {
    "label_order_generator": r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\scripts\radioml_clean_contract.py",
    "public_protocol_recovery": r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\scripts\radioml_independent_rx_contract.py",
    "v2_waveform": r"F:\嵌赛\fix10class24_waveform_correct_v2_work\scripts\radioml_v2_contract.py",
    "rf_constants": r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\scripts\radioml_dualsdr_common.py",
}
