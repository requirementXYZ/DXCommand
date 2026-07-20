"""In-memory spot store: dedupe/refresh, age-out, cap."""
from __future__ import annotations

import time

from .parser import Spot


class SpotStore:
    def __init__(self, max_age_s: int = 1800, max_count: int = 2000) -> None:
        self.max_age_s = max_age_s
        self.max_count = max_count
        self._spots: dict[str, Spot] = {}

    def add(self, spot: Spot) -> tuple[Spot, bool]:
        """Insert or refresh. Returns (stored_spot, is_new)."""
        self.prune()
        # Same call on the same band within 1 kHz refreshes the existing entry.
        for s in self._spots.values():
            if s.dx_call == spot.dx_call and s.band == spot.band and abs(s.freq - spot.freq) <= 1.0:
                s.ts = spot.ts
                s.freq = spot.freq
                s.spotter = spot.spotter
                s.comment = spot.comment or s.comment
                s.split_tx_khz = spot.split_tx_khz or s.split_tx_khz
                if spot.mode != "OTHER":
                    s.mode = spot.mode
                return s, False
        self._spots[spot.key()] = spot
        if len(self._spots) > self.max_count:
            oldest = min(self._spots.values(), key=lambda s: s.ts)
            del self._spots[oldest.key()]
        return spot, True

    def prune(self) -> list[str]:
        cutoff = time.time() - self.max_age_s
        stale = [k for k, s in self._spots.items() if s.ts < cutoff]
        for k in stale:
            del self._spots[k]
        return stale

    def all(self) -> list[Spot]:
        self.prune()
        return sorted(self._spots.values(), key=lambda s: -s.ts)
