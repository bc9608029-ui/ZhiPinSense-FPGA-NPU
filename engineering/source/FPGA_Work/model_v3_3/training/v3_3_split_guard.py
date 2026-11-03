"""Split-access guard enforcing the V3.3 data-isolation boundary.

Stage-1 candidate selection is a *development* activity and must never touch the
formal development test namespace (``"test"``) or the reserved final blind
namespace (``"v3_3_final_blind_test"``).  The former is only reachable by the
formal three-seed evaluation that runs *after* a candidate is frozen; the latter
is never reachable at all.

The guard has two jobs:

* **enforce** — while a selection scope is active, instantiating a forbidden
  split raises ``RuntimeError`` immediately, so a leak cannot silently proceed;
* **audit** — every split instantiation is recorded so Stage-1 can save an
  access audit that proves ``"test"`` and the final blind set were never touched.

The record is process-global and thread-safe.  ``record_split`` is called by the
V3.3 evaluation entry points (never by the frozen baseline dataset), so the audit
reflects exactly what V3.3 development code touched.
"""

from __future__ import annotations

import threading

FORBIDDEN_SPLITS = frozenset({"test", "v3_3_final_blind_test"})
SELECTION_VALIDATION_SPLIT = "v3_3_validation"

_lock = threading.Lock()
_active = False
_accessed: list[str] = []


def enter_selection_scope() -> None:
    """Arm the guard: forbidden splits now raise instead of being tolerated."""
    global _active
    with _lock:
        _active = True


def exit_selection_scope() -> list[str]:
    """Disarm the guard and return the full split-access audit for this scope."""
    global _active
    with _lock:
        _active = False
        return list(_accessed)


def record_split(split: str) -> None:
    """Record a dataset split instantiation; raise if it is forbidden while armed."""
    name = str(split)
    with _lock:
        _accessed.append(name)
        if _active and name in FORBIDDEN_SPLITS:
            raise RuntimeError(
                f"Split {name!r} is forbidden during selection scope; "
                f"only the validation namespace ({SELECTION_VALIDATION_SPLIT!r}) "
                f"may be used for candidate ranking."
            )


def accessed_splits() -> list[str]:
    with _lock:
        return list(_accessed)


def clear_accessed() -> None:
    with _lock:
        _accessed.clear()


def is_active() -> bool:
    with _lock:
        return _active
