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
from training.utils import resolve_project_path


def load_qam_aware_v3_2_config(path: str | Path) -> dict[str, Any]:
    """Merge baseline + V3.2 experiment + optional smoke overrides."""

    return load_qam_aware_v3_config(path)


def write_text_lf(path: str | Path, text: str) -> Path:
    """Write text with explicit LF line endings (no CRLF, no BOM).

    ``Path.write_text`` opens files in text mode with ``newline=None``, which on
    Windows translates ``\\n`` to ``\\r\\n``.  That corrupts the sha256 manifests
    and shell scripts consumed on Linux (``sha256sum -c``).  This helper forces
    ``newline="\\n"`` so the on-disk bytes are exactly LF.

    Kept here (not in ``training.utils``) because ``training.utils`` is a
    frozen Baseline V1 asset whose byte-for-byte content is locked by
    ``configs/baseline_v1_lock.json``.
    """

    destination = resolve_project_path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return destination
