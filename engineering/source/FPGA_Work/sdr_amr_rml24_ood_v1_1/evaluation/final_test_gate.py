"""One-time final-test access ledger (atomic, fail-closed).

The final evaluation reads the RadioML ``test`` split and the ``ood_final_test``
family exactly once each.  This module persists that access as a write-once
ledger so a duplicate final run is refused instead of silently re-reading (or,
worse, deleting old results and re-running).

The ledger is claimed with ``os.open(O_CREAT | O_EXCL)`` so two concurrent runs
cannot both acquire it, and it is completed with an atomic ``os.replace``.  A
second ``acquire_gate`` on a path that already carries ``STARTED`` or
``COMPLETE`` fails closed.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS_STARTED = "STARTED"
STATUS_COMPLETE = "COMPLETE"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_sha256(path: str | Path) -> str:
    """SHA-256 of a file's bytes (used to bind the ledger to the threshold manifest)."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gate(path: str | Path) -> dict[str, Any] | None:
    """Read the ledger if it exists (``None`` when absent)."""
    target = Path(path)
    if not target.is_file():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def acquire_gate(path: str | Path, *, run_id: str, checkpoint_sha256: str,
                 threshold_manifest_sha256: str, dataset_sha256: str) -> dict[str, Any]:
    """Claim the final-test access ledger (fail-closed on an existing claim)."""
    target = Path(path)
    payload: dict[str, Any] = {
        "run_id": run_id,
        "checkpoint_sha256": checkpoint_sha256,
        "threshold_manifest_sha256": threshold_manifest_sha256,
        "dataset_sha256": dataset_sha256,
        "started_at": _utcnow_iso(),
        "completed_at": None,
        "id_test_accessed": False,
        "ood_final_test_accessed": False,
        "status": STATUS_STARTED,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        existing = read_gate(target)
        status = (existing or {}).get("status", "?")
        raise RuntimeError(
            f"final test access already recorded (status={status!r}); "
            f"refusing to re-run (do not delete old results to re-run)"
        ) from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return payload


def complete_gate(path: str | Path, *, id_test_accessed: bool = True,
                  ood_final_test_accessed: bool = True) -> dict[str, Any]:
    """Mark a claimed ledger COMPLETE (atomic replace; must already be STARTED)."""
    target = Path(path)
    existing = read_gate(target)
    if existing is None:
        raise RuntimeError("cannot complete a final-test gate that was never acquired")
    if existing.get("status") != STATUS_STARTED:
        raise RuntimeError(f"final-test gate status is {existing.get('status')!r}, not STARTED")
    payload = dict(existing)
    payload["id_test_accessed"] = bool(id_test_accessed)
    payload["ood_final_test_accessed"] = bool(ood_final_test_accessed)
    payload["status"] = STATUS_COMPLETE
    payload["completed_at"] = _utcnow_iso()
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return payload


__all__ = [
    "STATUS_STARTED", "STATUS_COMPLETE", "file_sha256",
    "read_gate", "acquire_gate", "complete_gate",
]
