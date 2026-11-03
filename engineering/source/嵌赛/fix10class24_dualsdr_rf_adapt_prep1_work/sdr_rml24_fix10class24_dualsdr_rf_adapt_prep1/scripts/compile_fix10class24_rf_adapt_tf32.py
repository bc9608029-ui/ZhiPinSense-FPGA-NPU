#!/usr/bin/env python3
"""compile_fix10class24_rf_adapt_tf32.py -- compile the rf-adapt candidate to TF32.

Gated: runs only if the FP32 candidate beats the original on the independent test
split (--go-from).  Fail-closed: no model is emitted unless the iCraft compile
hook exits 0.  Output dir ``model_rml24_rfadapt_tf32/`` is NEW; it never
overwrites the sibling ``model_rml24_tf32/`` or the production ``model_rml24_bf16/``.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from rfadapt_compile_common import compile_main  # noqa: E402

if __name__ == "__main__":
    sys.exit(compile_main("tf32"))
