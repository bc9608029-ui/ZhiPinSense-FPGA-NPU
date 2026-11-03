"""pytest bootstrap: make scripts/ and tests/ importable from any cwd."""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for sub in ("", "scripts", "tests"):
    p = os.path.join(ROOT, sub)
    if p not in sys.path:
        sys.path.insert(0, p)
