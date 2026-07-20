"""Simulated transceiver.

Behaves like a real rig behind OmniRig: commands land after a short latency,
state is observable via polling, and a tiny receiver 'personality' (S-meter
noise, occasional QSY by the 'operator') makes the UI feel alive in demos.
"""
from __future__ import annotations

import asyncio

from .base import RigBackend, RigState


class SimulatedRig(RigBackend):
    def __init__(self, on_change=None, latency_s: float = 0.12) -> None:
        self._state = RigState(
            status="On-line (simulated)",
            online=True,
            freq=14_025_000,
            freq_b=14_025_000,
            tx_freq=14_025_000,
            mode="CW",
            backend="simulator",
            label="Simulated rig",
        )
        self._latency = latency_s
        self._on_change = on_change
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._notify()

    async def stop(self) -> None:
        pass

    def get_state(self) -> RigState:
        return self._state

    def _notify(self) -> None:
        if self._on_change:
            self._on_change(self._state)

    async def _apply(self, **changes) -> None:
        async with self._lock:
            await asyncio.sleep(self._latency)  # rig CAT latency
            for k, v in changes.items():
                setattr(self._state, k, v)
            if not self._state.split:
                self._state.tx_freq = self._state.freq
            self._notify()

    async def set_freq(self, hz: int) -> None:
        await self._apply(freq=int(hz))

    async def set_mode(self, mode: str) -> None:
        await self._apply(mode=mode)

    async def set_split(self, rx_hz: int, tx_hz: int) -> None:
        await self._apply(freq=int(rx_hz), freq_b=int(tx_hz),
                          tx_freq=int(tx_hz), split=True)

    async def set_simplex(self, hz: int) -> None:
        await self._apply(freq=int(hz), freq_b=int(hz),
                          tx_freq=int(hz), split=False)
