"""M0: the 12-class import must refuse the PENDING contract (fail-closed)."""

from __future__ import annotations

import pytest

from scripts.import_12class_checkpoint import import_12class


def test_pending_contract_blocks_import():
    with pytest.raises(RuntimeError, match="BLOCKED_12CLASS_CONTRACT"):
        import_12class("contracts/12class_import_contract.json", output_path=None)
