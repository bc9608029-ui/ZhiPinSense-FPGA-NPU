"""M27 confusable-class expert-model framework (spec §十二).

Only the *framework* is delivered at this stage.  The expert class groups are NOT
frozen — spec §十二 mandates waiting for the 24-class production model, then deriving
bidirectionally-confused groups from the frozen validation confusion matrix, training
experts on the training set only, choosing routing gates on validation, and touching
final-test exactly once.

Status is fixed to:
    EXPERT_MODEL_FRAMEWORK_READY
    24CLASS_EXPERT_MODEL_NOT_TRAINED

No expert model is trained here, and no QAM/PSK expert may be claimed complete.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

EXPERT_FRAMEWORK_STATUS = "EXPERT_MODEL_FRAMEWORK_READY"
EXPERT_MODEL_STATUS = "24CLASS_EXPERT_MODEL_NOT_TRAINED"

# Frozen 24-class label order (RadioML2018 24-class contract) — read-only reference.
LABEL_ORDER_24 = [
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
]

# Placeholder expert groups.  NOT FROZEN: these are illustrative and must be replaced
# by the groups derived from the frozen 24-class validation confusion matrix.
PLACEHOLDER_EXPERT_GROUPS = {
    "qam": [12, 13, 14, 15, 16],            # 16/32/64/128/256 QAM
    "psk": [3, 4, 5, 6, 7],                 # BPSK/QPSK/8/16/32 PSK
    "apsk": [8, 9, 10, 11],                 # 16/32/64/128 APSK
    "am_dsb": [18, 19, 20],                 # AM-DSB-WC/SC + AM-SSB? (illustrative)
}


def find_confusable_pairs(cm, min_ratio=0.05):
    """From a (24x24) confusion-matrix count array, return the bidirectionally
    confused pairs (i, j), i<j, where both off-diagonal rates exceed min_ratio.

    This is the *tool*; it must only be run on the frozen 24-class validation
    confusion matrix once that model exists.
    """
    cm = np.asarray(cm, dtype=np.float64)
    n = cm.shape[0]
    pairs = []
    for i in range(n):
        row_sum = cm[i].sum()
        for j in range(i + 1, n):
            col_sum = cm[:, j].sum()
            if row_sum <= 0 or col_sum <= 0:
                continue
            rate_ij = cm[i, j] / row_sum
            rate_ji = cm[j, i] / col_sum
            if rate_ij >= min_ratio and rate_ji >= min_ratio:
                pairs.append((i, j))
    return pairs


def build_expert_label_map(groups, label_order):
    """Map expert-group member labels to a local (group-relative) index."""
    mapping = {}
    for group_name, members in groups.items():
        for local_i, global_i in enumerate(members):
            mapping[global_i] = (group_name, local_i, label_order[global_i])
    return mapping


def routing_gate():
    """Expert routing gate: refuses to route to a trained expert until the 24-class
    model is frozen.  Returns (status, message)."""
    return EXPERT_MODEL_STATUS, (
        "24-class production model not frozen; expert class groups and routing "
        "gates must be derived from the frozen validation confusion matrix"
    )


class ExpertStub(nn.Module):
    def __init__(self, n_classes=2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(1, 8, kernel_size=(1, 3), padding=(0, 1)),
            nn.ReLU(),
            nn.MaxPool2d((1, 2)),
            nn.Flatten(),
            nn.Linear(8 * 2 * 512, 32),
            nn.ReLU(),
            nn.Linear(32, n_classes),
        )

    def forward(self, x):
        return self.net(x.unsqueeze(1))


def export_expert_onnx(model, path, dummy_n=1):
    import torch
    model.eval()
    torch.onnx.export(
        model, torch.zeros(dummy_n, 2, 1024), path,
        input_names=["iq"], output_names=["expert_logits"],
        opset_version=13, do_constant_folding=True, dynamo=False,
    )
    return path


def npu_operator_audit(onnx_path, supported_ops):
    import onnx
    m = onnx.load(onnx_path)
    unsupported = sorted({n.op_type for n in m.graph.node
                          if n.op_type not in supported_ops})
    return (len(unsupported) == 0), unsupported
