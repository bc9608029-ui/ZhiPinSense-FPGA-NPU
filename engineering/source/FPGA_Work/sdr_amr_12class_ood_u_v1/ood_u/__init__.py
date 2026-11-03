"""12-class semantic OOD-U (UNKNOWN rejection) package for the current NPU model.

This package adds CPU-side unknown-class rejection on top of the frozen
``12CLASS_CHAIN_VALIDATION_MODEL`` (``model_sha=2ae95275…``).  It reuses the shared
``ood`` scoring/metrics/energy primitives and the 12-class synthetic generator,
and layers the M20-specific contract, three-split data isolation, generator-
shortcut audit, threshold freeze, known-class (OOD-R) protection, and the final
blind test on top.
"""

from __future__ import annotations

__all__: list[str] = []
