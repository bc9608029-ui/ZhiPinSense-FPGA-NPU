"""M4/M5: model I/O contract — [B, 2, 1024] fp32 in, raw 24 logits out."""

from __future__ import annotations

import pytest
import torch

from contracts.rml24_contract import INPUT_SHAPE, OUTPUT_DIM
from models.rml24_net import RML24Classifier, build_rml24_model


def test_io_contract_constants():
    assert INPUT_SHAPE == (1, 2, 1024)
    assert OUTPUT_DIM == 24


def test_forward_shape():
    model = build_rml24_model(24)
    model.eval()
    iq = torch.randn(4, 2, 1024)
    with torch.inference_mode():
        logits, denoised = model(iq)
    assert logits.shape == (4, 24)
    assert denoised.shape == (4, 2, 1024)


def test_classifier_wrapper_returns_raw_logits():
    model = build_rml24_model(24).eval()
    wrapper = RML24Classifier(model)
    iq = torch.randn(2, 2, 1024)
    with torch.inference_mode():
        logits = wrapper(iq)
    assert logits.shape == (2, 24)
    assert torch.isfinite(logits).all()
    # Raw logits, no softmax: they may be negative and do not sum to one.
    assert torch.any(logits < 0.0)


def test_default_num_classes_is_24():
    assert build_rml24_model().num_classes == 24


def test_wrong_num_classes_rejected():
    with pytest.raises(ValueError):
        build_rml24_model(12)
