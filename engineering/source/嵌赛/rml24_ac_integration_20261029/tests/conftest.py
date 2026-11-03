"""Pytest conftest for the AC integration tree.

Makes the copied C-line tests (``tests/c_multisignal/``) run against the
FLAT-DEPLOYED ``multisignal_*`` modules (``overlay/rml24_final/runtime``) + the
BASE dependencies (``local_base/``) instead of the C-line dev tree
(``reference/`` + ``integration/`` + ``src/``).  The C-line import names
(``receiver_entry``, ``src.*``) are aliased to the flat modules via
``sys.modules`` so the copied tests run unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[1]

for p in (
    TREE / "overlay/rml24_final/runtime",
    TREE / "overlay/rml24_final/board_runtime",
    TREE / "local_base/runtime",
    TREE / "local_base/recovery",
    TREE / "local_base/board_runtime",
    TREE / "tests/support",
):
    sys.path.insert(0, str(p))

# Alias C-line module names -> flat-deployed modules.
import multisignal_contracts  # noqa: E402
import multisignal_psd  # noqa: E402
import multisignal_scan_adapter  # noqa: E402
import multisignal_tracker  # noqa: E402
import multisignal_receiver_entry  # noqa: E402
import multisignal_ui_model  # noqa: E402
import multisignal_scoring  # noqa: E402

_src = type(sys)("src")
_src.__path__ = []  # type: ignore[attr-defined]
_src.contracts = multisignal_contracts  # type: ignore[attr-defined]
_src.psd = multisignal_psd  # type: ignore[attr-defined]
_src.scan_adapter = multisignal_scan_adapter  # type: ignore[attr-defined]
_src.tracker = multisignal_tracker  # type: ignore[attr-defined]
_src.ui_model = multisignal_ui_model  # type: ignore[attr-defined]
_src.scoring = multisignal_scoring  # type: ignore[attr-defined]

sys.modules.setdefault("src", _src)
sys.modules["src.contracts"] = multisignal_contracts
sys.modules["src.psd"] = multisignal_psd
sys.modules["src.scan_adapter"] = multisignal_scan_adapter
sys.modules["src.tracker"] = multisignal_tracker
sys.modules["src.ui_model"] = multisignal_ui_model
sys.modules["src.scoring"] = multisignal_scoring
sys.modules["receiver_entry"] = multisignal_receiver_entry
