"""Configuration helpers for the independent QAM-Aware V3.2 track.

V3.2 shares V3's baseline-merge and frozen-contract checks verbatim (class
order, 1024-sample frame, 3 physical channels).  Reusing the loader avoids a
second copy of the same contract code; the loader itself is V3.2-agnostic and
reads everything from the requested YAML path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from training.qam_aware_v3_utils import load_qam_aware_v3_config


def load_qam_aware_v3_2_config(path: str | Path) -> dict[str, Any]:
    """Merge baseline + V3.2 experiment + optional smoke overrides."""

    return load_qam_aware_v3_config(path)
