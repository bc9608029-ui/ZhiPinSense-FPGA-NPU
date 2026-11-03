"""pytest bootstrap: expose the ``src`` package to the test modules."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
