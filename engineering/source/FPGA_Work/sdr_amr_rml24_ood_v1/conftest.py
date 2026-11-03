"""Pytest bootstrap.

Put the project root on ``sys.path`` so the tests can import the top-level
packages (``contracts``, ``ood``, ``models``, ``datasets``, ``training``, ...)
regardless of whether pytest is invoked as ``python -m pytest`` or bare ``pytest``.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
