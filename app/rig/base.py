"""Rig abstraction shared by the OmniRig COM backend and the simulator."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field

# Canonical mode names used throughout the app
MODES = ("CW", "CW-R", "USB", "LSB", "DATA-U", "DATA-L", "AM", "FM")


@dataclass
class RigState:
    status: str = "Off-line"       # human-readable status string
    online: bool = False
    freq: int = 0                  # RX (VFO A) frequency, Hz
    freq_b: int = 0                # VFO B frequency, Hz
    tx_freq: int = 0               # effective TX frequency, Hz
    mode: str = "CW"
    split: bool = False
    tx: bool = False
    rit: int = 0
    backend: str = "simulator"
    label: str = "Rig"
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class RigBackend(ABC):
    """All frequency arguments are in Hz."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    def get_state(self) -> RigState: ...

    @abstractmethod
    async def set_freq(self, hz: int) -> None: ...

    @abstractmethod
    async def set_mode(self, mode: str) -> None: ...

    @abstractmethod
    async def set_split(self, rx_hz: int, tx_hz: int) -> None:
        """Enable split with the given RX/TX pair."""

    @abstractmethod
    async def set_simplex(self, hz: int) -> None:
        """Drop split, set both VFOs to hz."""

    async def tune(self, freq_hz: int, mode: str | None = None,
                   split_tx_hz: int | None = None) -> None:
        """One-click tune from a spot: frequency, optional mode, optional split."""
        if split_tx_hz:
            await self.set_split(freq_hz, split_tx_hz)
        else:
            await self.set_simplex(freq_hz)
        if mode:
            await self.set_mode(mode if mode in MODES else mode_for_spot(mode))


def mode_for_spot(spot_mode: str) -> str:
    """Map a spot/decode mode to the rig mode to select."""
    if spot_mode in ("FT8", "FT4", "RTTY", "DIGI"):
        return "DATA-U"
    if spot_mode == "CW":
        return "CW"
    if spot_mode == "SSB":
        return "USB"  # caller may refine by band; DX chasing default
    return "CW"
