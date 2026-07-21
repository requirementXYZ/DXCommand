"""Simulated WSJT-X: produces realistic FT8 decode cycles without a radio.

Feeds Decode/Status objects into the same callbacks the UDP listener uses,
aligned to real 15-second FT8 periods, including the demo DXpedition running
Fox/Hound and a mix of everyday CQs.
"""
from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime, timezone

from .protocol import Decode, Status

CALLS = ["JA1NUT", "ZL4AS", "VK9XCX", "5Z4VJ", "FK8IK", "HB9CVQ", "PY2XB",
         "9M2TO", "TF3JB", "A25RU", "E51DWC", "V47JA", "K1ABC", "W6XYZ",
         "DL2CC", "G4FOX", "SM5AAA", "OH2XX", "F5NN", "EA3ZZ", "VE3KP",
         "JW6VDA", "ZD7BG", "UN7AB", "4X1DX"]
GRIDS = ["PM95", "RE66", "OH29", "KI88", "RG37", "JN47", "GG66", "OJ05",
         "HP94", "KG25", "BG08", "FK87", "FN42", "CM97", "JO62", "IO91"]
FOX = "3Y0K"


class WsjtxSimulator:
    def __init__(self, on_decode, on_status, my_call: str = "N0CALL") -> None:
        self.on_decode = on_decode
        self.on_status = on_status
        self.my_call = my_call
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="wsjtx-sim")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    def _messages(self) -> list[str]:
        msgs = [f"CQ {FOX} JD59"]  # the DXpedition fox
        for _ in range(random.randint(4, 12)):
            kind = random.random()
            call = random.choice(CALLS)
            grid = random.choice(GRIDS)
            if kind < 0.35:
                msgs.append(f"CQ {call} {grid}")
            elif kind < 0.55:
                msgs.append(f"{FOX} {call} {grid}")          # hounds calling
            elif kind < 0.7:
                msgs.append(f"{call} {FOX} RR73")            # fox working
            elif kind < 0.85:
                a, b = random.sample(CALLS, 2)
                msgs.append(f"{a} {b} {random.choice(['-08', '+02', 'R-15', 'RRR', '73'])}")
            else:
                msgs.append(f"CQ DX {call} {grid}")
        return msgs

    async def _run(self) -> None:
        client = "WSJT-X-sim"
        while True:
            try:
                # Wait for the start of the next 15 s FT8 period, then "decode".
                now = time.time()
                await asyncio.sleep(15 - (now % 15) + random.uniform(0.5, 1.5))
                utc = datetime.now(timezone.utc)
                ms = (utc.hour * 3600 + utc.minute * 60 + utc.second) * 1000
                for msg in self._messages():
                    self.on_decode(Decode(
                        client_id=client, is_new=True, time_ms=ms,
                        snr=random.randint(-22, 8),
                        delta_t=round(random.uniform(-0.5, 0.5), 1),
                        delta_f=random.randint(200, 2800),
                        mode="~", message=msg))
                    await asyncio.sleep(random.uniform(0.02, 0.12))
                self.on_status(Status(
                    client_id=client, dial_freq=14_090_000, mode="FT8",
                    dx_call=FOX, decoding=False, de_call=self.my_call,
                    de_grid="IO95", dx_grid="JD59"))
            except asyncio.CancelledError:
                return
