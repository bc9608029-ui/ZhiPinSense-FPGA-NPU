"""One-time closed-set final-test access ledger (atomic, fail-closed).

The closed-set ID ``test`` access and the OOD ``ood_final_test`` access are two
**fully independent** ledgers.  ``--closed-set-only`` uses this ledger
(``runs/final_evaluation/rml24_closed_set_test_access.json``) and must never create
or touch the OOD final ledger (``final_test_access.json``), so the 24-class
closed-set model can be evaluated once without ever instantiating the not-yet-ready
OOD-U final test.

The ledger is claimed with ``os.open(O_CREAT | O_EXCL)`` (atomic, two concurrent
runs cannot both acquire it) and completed with ``os.replace``.  A second
``acquire_closed_set_gate`` on a path already carrying ``STARTED`` or ``COMPLETE``
fails closed, and ``ood_final_test_accessed`` is always ``false``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS_STARTED = "STARTED"
STATUS_COMPLETE = "COMPLETE"
SCHEMA_VERSION = 1
MODE_CLOSED_SET_ONLY = "closed_set_only"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_closed_set_gate(path: str | Path) -> dict[str, Any] | None:
    """Read the closed-set ledger if it exists (``None`` when absent)."""
    target = Path(path)
    if not target.is_file():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def acquire_closed_set_gate(
    path: str | Path,
    *,
    run_id: str,
    checkpoint_path: str,
    checkpoint_sha256: str,
    dataset_sha256: str,
    label_contract_sha256: str,
    config_sha256: str,
) -> dict[str, Any]:
    """Claim the closed-set access ledger (fail-closed on an existing claim)."""
    target = Path(path)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "mode": MODE_CLOSED_SET_ONLY,
        "checkpoint_path": checkpoint_path,
        "checkpoint_sha256": checkpoint_sha256,
        "dataset_sha256": dataset_sha256,
        "label_contract_sha256": label_contract_sha256,
        "config_sha256": config_sha256,
        "started_at": _utcnow_iso(),
        "completed_at": None,
        "id_test_accessed": False,
        "ood_final_test_accessed": False,
        "status": STATUS_STARTED,
        "output_sha256": None,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        existing = read_closed_set_gate(target)
        status = (existing or {}).get("status", "?")
        raise RuntimeError(
            f"closed-set test access already recorded (status={status!r}); "
            f"refusing to re-run (do not delete old results to re-run)"
        ) from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return payload


def complete_closed_set_gate(path: str | Path, *, output_sha256: str) -> dict[str, Any]:
    """Mark a claimed closed-set ledger COMPLETE (atomic replace).

    ``ood_final_test_accessed`` stays ``false`` — this ledger only ever records the
    closed-set ID test access, never the OOD final test.
    """
    target = Path(path)
    existing = read_closed_set_gate(target)
    if existing is None:
        raise RuntimeError("cannot complete a closed-set gate that was never acquired")
    if existing.get("status") != STATUS_STARTED:
        raise RuntimeError(f"closed-set gate status is {existing.get('status')!r}, not STARTED")
    payload = dict(existing)
    payload["id_test_accessed"] = True
    payload["ood_final_test_accessed"] = False
    payload["output_sha256"] = output_sha256
    payload["status"] = STATUS_COMPLETE
    payload["completed_at"] = _utcnow_iso()
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return payload


__all__ = [
    "STATUS_STARTED", "STATUS_COMPLETE", "SCHEMA_VERSION", "MODE_CLOSED_SET_ONLY",
    "read_closed_set_gate", "acquire_closed_set_gate", "complete_closed_set_gate",
]
