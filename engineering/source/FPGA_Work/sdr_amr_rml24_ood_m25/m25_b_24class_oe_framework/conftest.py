"""Pytest bootstrap for the M25-B 24-class OE framework.

Puts the project root on ``sys.path`` so tests can import the top-level packages
(``contracts``, ``datasets``, ``audit``, ``ood``, ``training``, ``npu_boundary``).
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
