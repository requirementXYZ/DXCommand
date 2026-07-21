"""DXpedition scenario spot simulator.

Generates a believable cluster feed for demos and testing: a rare-entity
DXpedition running split CW and F/H FT8, plus everyday DX activity across
bands, all emitted as Spot objects through the same callback the real
cluster client uses.
"""
from __future__ import annotations

import asyncio
import random
import time

from .parser import Spot, band_for, classify_mode, split_hint

SPOTTERS = ["W3LPL", "K3LR", "VE7CC", "G4IRN", "DL8LAS", "JA1TRC", "K1TTT",
            "OH6BG", "N6TV", "VK3MO", "ZL2IFB", "SM7IUN", "F6BEE", "EA5WU"]

# (call, freq_khz, mode, comment pool, weight)
DXPEDITION = [
    ("3Y0K", 14023.0, "CW", ["UP 2 big pileup", "UP 2", "loud in EU UP 2.5", "QSX 14025.2"], 6),
    ("3Y0K", 10108.0, "CW", ["UP 1", "UP", "gud sigs NA UP 1.5"], 3),
    ("3Y0K", 14090.0, "FT8", ["FT8 F/H", "F/H NA now", "FT8 fox up"], 5),
    ("3Y0K", 18095.0, "FT8", ["FT8 F/H", "F/H"], 3),
    ("VP8PIE", 21024.0, "CW", ["UP 2", "QSX 21026.0 wkg EU"], 3),
    ("VP8PIE", 21091.0, "FT8", ["FT8 F/H"], 2),
]

REGULAR = [
    ("JA1NUT", 14012.5, "CW", ["cq dx", "5nn tu"], 2),
    ("ZL4AS", 7008.0, "CW", ["gud sig", "cq"], 1),
    ("VK9XCX", 18078.5, "CW", ["UP 1", "nice sig"], 2),
    ("5Z4VJ", 21074.0, "FT8", ["FT8 -12", "FT8 tnx"], 2),
    ("FK8IK", 14074.0, "FT8", ["FT8", "FT8 -08"], 2),
    ("HB9CVQ", 10118.0, "CW", ["cq eu", ""], 1),
    ("PY2XB", 24894.5, "CW", ["cq dx", ""], 1),
    ("9M2TO", 28074.0, "FT8", ["FT8 +02", "FT8"], 1),
    ("TF3JB", 7074.0, "FT8", ["FT8", ""], 1),
    ("A25RU", 21014.0, "CW", ["UP 1", "cq up"], 2),
    ("E51DWC", 14040.0, "CW", ["cq pac", ""], 1),
    ("CE0YHF", 28024.0, "CW", ["cq", ""], 1),
    ("V47JA", 18100.0, "FT8", ["FT8", ""], 1),
    ("JW6VDA", 14080.0, "FT4", ["FT4", ""], 1),
    ("ZD7BG", 21290.0, "SSB", ["59 tnx", "cq dx"], 1),
]


class SpotSimulator:
    def __init__(self, on_spot, on_status, interval_range=(1.5, 4.0)) -> None:
        self.on_spot = on_spot
        self.on_status = on_status
        self.interval_range = interval_range
        self._task: asyncio.Task | None = None
        self._pool = [(e, w) for e in (DXPEDITION + REGULAR) for w in [e[4]]]

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="spot-sim")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    def make_spot(self) -> Spot:
        entries, weights = zip(*[((c, f, m, com), w)
                                 for c, f, m, com, w in DXPEDITION + REGULAR])
        call, freq, mode, comments = random.choices(entries, weights=weights)[0]
        freq = round(freq + random.uniform(-0.3, 0.3), 1)
        comment = random.choice(comments)
        spotter = random.choice(SPOTTERS)
        snr = None
        # ~40% of CW traffic arrives as RBN skimmer spots (CW Skimmer heritage)
        if mode == "CW" and random.random() < 0.4:
            snr = random.randint(6, 38)
            wpm = random.randint(18, 34)
            spotter = random.choice(SPOTTERS)
            comment = f"CW {snr} dB {wpm} WPM CQ"
        spot = Spot(
            dx_call=call, freq=freq, spotter=spotter,
            comment=comment, band=band_for(freq),
            mode=mode if mode != "SSB" else classify_mode(freq, comment),
            split_tx_khz=split_hint(freq, comment),
            ts=time.time(), source="simulator", snr=snr,
        )
        spot.spotters = [{"call": spotter, "cont": None, "snr": snr, "ts": spot.ts}]
        return spot

    async def _run(self) -> None:
        self.on_status("simulated cluster feed (demo mode)")
        # Seed an initial burst so the UI is populated immediately.
        for _ in range(25):
            spot = self.make_spot()
            spot.ts = time.time() - random.uniform(0, 900)
            self.on_spot(spot)
        while True:
            try:
                await asyncio.sleep(random.uniform(*self.interval_range))
                self.on_spot(self.make_spot())
            except asyncio.CancelledError:
                return
