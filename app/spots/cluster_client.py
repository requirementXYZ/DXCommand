"""Asyncio telnet client for DX cluster nodes (DXSpider, CC Cluster, AR-Cluster,
or a local PskrDxClusterService instance)."""
from __future__ import annotations

import asyncio
import re

from .parser import parse_spot_line, Spot

LOGIN_PROMPT = re.compile(r"(login|call(sign)?)\s*[:>]?\s*$", re.I)


class ClusterClient:
    def __init__(self, host: str, port: int, callsign: str,
                 on_spot, on_status) -> None:
        self.host, self.port, self.callsign = host, port, callsign
        self.on_spot = on_spot            # callable(Spot)
        self.on_status = on_status        # callable(str)  connected/disconnected/...
        self._task: asyncio.Task | None = None
        self._stop = False

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="cluster")

    async def stop(self) -> None:
        self._stop = True
        if self._task:
            self._task.cancel()

    async def _run(self) -> None:
        backoff = 2
        while not self._stop:
            try:
                self.on_status(f"connecting to {self.host}:{self.port}")
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), timeout=15)
                self.on_status("connected")
                backoff = 2
                sent_login = False
                buf = b""
                while not self._stop:
                    chunk = await asyncio.wait_for(reader.read(4096), timeout=600)
                    if not chunk:
                        raise ConnectionError("closed by server")
                    buf += chunk.replace(b"\xff\xfb", b"").replace(b"\xff\xfd", b"")
                    if not sent_login and LOGIN_PROMPT.search(
                            buf[-80:].decode("utf-8", "ignore")):
                        writer.write((self.callsign + "\r\n").encode())
                        await writer.drain()
                        sent_login = True
                        self.on_status(f"logged in as {self.callsign}")
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        spot = parse_spot_line(line.decode("utf-8", "ignore"))
                        if spot:
                            self.on_spot(spot)
            except asyncio.CancelledError:
                return
            except Exception as exc:  # noqa: BLE001 - network errors of all kinds
                self.on_status(f"disconnected ({exc}); retrying in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
