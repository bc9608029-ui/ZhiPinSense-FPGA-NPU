"""Fail-closed RX-LO tuning adapter for the legacy Pluto ``Radio`` wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _read_attr(radio: Any, channel: Any, name: str) -> int:
    getter = getattr(radio, "get", None)
    if callable(getter):
        return int(float(getter(channel, name)))
    attrs = getattr(channel, "attrs", None)
    if attrs is not None and name in attrs:
        return int(float(attrs[name].value))
    value = getattr(channel, name, None)
    if value is not None:
        return int(float(getattr(value, "value", value)))
    raise RuntimeError(f"radio wrapper cannot read {name}")


@dataclass
class RxLoController:
    radio: Any
    tolerance_hz: int = 5_000
    flush_captures: int = 2

    def __post_init__(self) -> None:
        if self.tolerance_hz < 0 or self.flush_captures < 0:
            raise ValueError("invalid LO controller limits")
        if not hasattr(self.radio, "set") or not hasattr(self.radio, "rlo"):
            raise RuntimeError("legacy Radio lacks set()/rlo required for scan")
        self.original_hz = _read_attr(self.radio, self.radio.rlo, "frequency")
        self.current_hz = self.original_hz

    def tune(self, frequency_hz: int) -> int:
        requested = int(frequency_hz)
        self.radio.set(self.radio.rlo, "frequency", requested)
        actual = _read_attr(self.radio, self.radio.rlo, "frequency")
        if abs(actual - requested) > self.tolerance_hz:
            raise RuntimeError(f"RX LO readback mismatch requested={requested} actual={actual}")
        self.current_hz = actual
        return actual

    def flush(self) -> None:
        for _ in range(self.flush_captures):
            self.radio.receive(65536)

    def restore(self) -> None:
        self.tune(self.original_hz)

