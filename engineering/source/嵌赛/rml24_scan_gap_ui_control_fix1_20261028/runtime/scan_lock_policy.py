"""Label-blind hysteresis for the passive band-scan lock.

The RF validation showed that three transient public-frame misses triggered an
11-point full sweep.  A sweep took about 20 s and therefore skipped following
6 s transmit slots.  This policy keeps the last verified LO for a bounded
number of misses and a minimum continuous-miss duration before permitting a
full rescan. It never reads a label, payload, classifier output, or expected
frequency.
"""

from __future__ import annotations


class LockHysteresis:
    def __init__(self, misses_before_rescan: int = 5,
                 minimum_miss_seconds: float = 1.0) -> None:
        if misses_before_rescan < 1:
            raise ValueError("misses_before_rescan must be positive")
        if minimum_miss_seconds < 0:
            raise ValueError("minimum_miss_seconds must be non-negative")
        self.limit = int(misses_before_rescan)
        self.minimum_miss_seconds = float(minimum_miss_seconds)
        self.misses = 0
        self.first_miss_time = None

    def hit(self) -> None:
        self.misses = 0
        self.first_miss_time = None

    def miss(self, now_seconds: float) -> bool:
        """Record one failed locked-frequency capture.

        Returns True only when a full-band rescan is now allowed.
        """
        if self.first_miss_time is None:
            self.first_miss_time = float(now_seconds)
        self.misses += 1
        elapsed = max(0.0, float(now_seconds) - self.first_miss_time)
        return self.misses >= self.limit and elapsed >= self.minimum_miss_seconds

    def reset(self) -> None:
        self.hit()

