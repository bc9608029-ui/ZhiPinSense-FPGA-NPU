"""M27 channel/interference recognition — frozen contract (spec §十一).

This is a *synthetic-data prototype*.  It may only be labelled
``CHANNEL_IMPAIRMENT_MODEL_SYNTHETIC_PROTOTYPE`` — never "real wireless environment
recognition".  Input contract is [N,2,1024] planar I/Q, RMS ~= 1, no normalization.
The 11 environment labels are frozen in the order below; the known modulation classes
inside each environment are balanced by the generator (never leak the label).
"""

# Frozen environment labels (order is part of the contract).
CHANNEL_LABELS = [
    "CLEAN",
    "CFO",
    "PHASE_NOISE",
    "IQ_IMBALANCE",
    "MULTIPATH",
    "CLIPPING",
    "CW_INTERFERENCE",
    "MULTITONE",
    "PULSE",
    "SWEEP",
    "MULTI_IMPAIRMENT",
]
NUM_CHANNEL_LABELS = len(CHANNEL_LABELS)  # 11

# Known modulation classes, balanced across every environment label.
MODULATION_POOL = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "GFSK"]

# Input/output contract.
INPUT_CONTRACT = "[N,2,1024] planar IQ, RMS~1, no normalization"
OUTPUT_CONTRACT = "11 x float32 raw logits (channel/environment)"

# Split codes for 3-way seed isolation.
SPLIT_TRAIN = 0
SPLIT_VALIDATION = 1
SPLIT_FINAL_TEST = 2
SPLIT_NAMES = {SPLIT_TRAIN: "train", SPLIT_VALIDATION: "validation",
               SPLIT_FINAL_TEST: "final_test"}

# Forbidden status markers (gate audit).  The prototype must never claim these.
FORBIDDEN_STATUS_MARKERS = (
    "CHANNEL_IMPAIRMENT_MODEL_DONE",
    "REAL_ENVIRONMENT_RECOGNITION_COMPLETE",
    "HARDWARE_PASS",
    "PERFORMANCE_PASS",
    "PROJECT_COMPLETE",
    "FINAL_MODEL_PASS",
    "FINAL_CHANNEL_PASS",
)

# Only status this prototype is permitted to claim.
ALLOWED_STATUS = "CHANNEL_IMPAIRMENT_MODEL_SYNTHETIC_PROTOTYPE"

# NPU / int8-supported operator whitelist (used by the int8-feasibility check).
SUPPORTED_OPS = {
    "Conv", "Relu", "MaxPool", "Flatten", "Gemm", "MatMul", "Add", "Softmax",
    "Constant", "Reshape", "Transpose", "Gather", "Unsqueeze", "Squeeze",
    "QuantizeLinear", "DequantizeLinear", "ConvInteger", "Clip", "Mul",
}


def label_index(label: str) -> int:
    return CHANNEL_LABELS.index(label)
