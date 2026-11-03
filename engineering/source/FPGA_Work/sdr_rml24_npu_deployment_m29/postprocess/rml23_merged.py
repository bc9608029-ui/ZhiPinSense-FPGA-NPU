"""M29 Phase F1 — 23-class AM-SSB merged post-processing (reference).

Takes NPU/FP32 raw 24-dim logits and produces the deployed 23-class result:

    merged[17] = logaddexp(logit_AM_SSB_SC, logit_AM_SSB_WC)
               = log( exp(logit_SC) + exp(logit_WC) )

All other dims are copied in place; dims 19..23 shift down by one.  The raw
24-dim logits are ALWAYS preserved by the caller path (they are the source of
truth); this module only *adds* the merged view, it never destroys the 24-dim.

Fail-closed behaviour:
  * input not 24-dim        -> ValueError
  * any NaN / +/-Inf input  -> ValueError (non-finite logits are rejected)

Pure stdlib for the scalar path (importable under ``python -I``); the numpy
vectorized path imports numpy lazily so the module stays stdlib-only.
"""
from __future__ import annotations

import math
import os
import sys

# The contract lives one directory up; import it without hard-coding cwd so the
# module works whether imported as a package member or run directly.
_CONTRACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "contracts")
if _CONTRACT_DIR not in sys.path:
    sys.path.insert(0, _CONTRACT_DIR)

from rml23_merged_contract import (  # noqa: E402
    AMSSB_SOURCE_SC,
    AMSSB_SOURCE_WC,
    DEPLOYED_CLASS_COUNT,
    DEPLOYED_LABEL_ORDER_23,
    NPU_OUTPUT_DIM,
    SOURCE_TO_DEPLOYED,
)

_NEG_INF = float("-inf")
_POS_INF = float("inf")


def logaddexp(a: float, b: float) -> float:
    """Numerically-stable log(exp(a) + exp(b)).

    Correct at the infinities: logaddexp(-inf, x) == x; logaddexp(+inf, x) == +inf;
    logaddexp(-inf, -inf) == -inf.  NaN propagates (callers reject NaN upstream).
    """
    if a == _NEG_INF:
        return b
    if b == _NEG_INF:
        return a
    if a == _POS_INF or b == _POS_INF:
        return _POS_INF
    m = max(a, b)
    return m + math.log1p(math.exp(min(a, b) - m))


def validate_logits24(logits) -> None:
    """Fail closed unless ``logits`` is 24 finite floats."""
    if len(logits) != NPU_OUTPUT_DIM:
        raise ValueError(
            f"rml23_merged expects {NPU_OUTPUT_DIM}-dim raw logits, got {len(logits)}"
        )
    for v in logits:
        if not math.isfinite(float(v)):
            raise ValueError(f"rml23_merged rejects non-finite logit {v!r}")


def merge_logits_24_to_23(logits24) -> list:
    """24-dim raw logits -> 23-dim merged logits (list of 23 floats).

    Preserves every raw value; only the AM-SSB slot is a log-space merge.
    """
    validate_logits24(logits24)
    out = [0.0] * DEPLOYED_CLASS_COUNT
    for src in range(NPU_OUTPUT_DIM):
        dst = SOURCE_TO_DEPLOYED[src]
        if src == AMSSB_SOURCE_SC:
            # second AM-SSB source: fold into the merged slot via logaddexp
            out[dst] = logaddexp(float(out[dst]), float(logits24[src]))
        else:
            out[dst] = float(logits24[src])
    # The WC slot (index 17) is written first, then SC folds into it.
    return out


def predict_23(logits24) -> tuple:
    """Returns (deployed_index, label) for the merged 23-class argmax."""
    merged = merge_logits_24_to_23(logits24)
    idx = max(range(DEPLOYED_CLASS_COUNT), key=lambda i: merged[i])
    return idx, DEPLOYED_LABEL_ORDER_23[idx]


def predict_23_full(logits24) -> dict:
    """Deployment result record: raw 24-dim top-1 + merged 23-class top-1.

    Keeps the raw 24-dim view alongside the merged view (F4 result log contract):
    raw_24_top1, merged_23_top1, deployment_mode, expert_enabled=false.
    """
    validate_logits24(logits24)
    raw_24_top1 = max(range(NPU_OUTPUT_DIM), key=lambda i: float(logits24[i]))
    merged_idx, merged_label = predict_23(logits24)
    return {
        "raw_24_top1": int(raw_24_top1),
        "merged_23_top1": int(merged_idx),
        "merged_23_label": merged_label,
        "deployment_mode": "AMSSB_MERGED",
        "expert_enabled": False,
        "expert_result": "NOT_RUN",
    }


def merge_many_24_to_23(logits_matrix):
    """Vectorized merge for a (N, 24) array -> (N, 23) numpy array.

    Uses the exact same ``logaddexp`` semantics as the scalar path.  numpy is
    imported lazily so the module remains stdlib-importable.
    """
    import numpy as np
    a = np.asarray(logits_matrix, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] != NPU_OUTPUT_DIM:
        raise ValueError(
            f"merge_many expects (N, {NPU_OUTPUT_DIM}), got {a.shape}"
        )
    if not np.isfinite(a).all():
        raise ValueError("rml23_merged rejects non-finite logits")
    out = np.empty((a.shape[0], DEPLOYED_CLASS_COUNT), dtype=np.float64)
    # copy the two non-shifted blocks, drop SC, then fold WC+SC by logaddexp
    out[:, :17] = a[:, :17]
    out[:, 18:] = a[:, 19:]
    sc = a[:, AMSSB_SOURCE_SC]
    wc = a[:, AMSSB_SOURCE_WC]
    m = np.maximum(sc, wc)
    # logaddexp(sc, wc) = m + log1p(exp(min(sc,wc) - m)), matches the scalar path
    with np.errstate(over="ignore", invalid="ignore"):
        merged = m + np.log1p(np.exp(np.minimum(sc, wc) - m))
    # at m == -inf both are -inf -> -inf; at m == +inf -> +inf
    merged[(sc == -np.inf) & (wc == -np.inf)] = -np.inf
    out[:, AMSSB_SOURCE_WC] = merged
    return out
