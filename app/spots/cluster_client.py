"""Asyncio telnet client for DX cluster nodes (DXSpider, CC Cluster, AR-Cluster,
or a local PskrDxClusterService instance)."""
from __future__ import annotations

import asyncio
import re

from .parser import parse_spot_line, Spot

LOGIN_PROMPT = re.compile(r"(login|call(sign)?)\s*[:>]?\s*$", re.I)
REJECTED = re.compile(r"not a valid call|invalid call|bad call|access denied", re.I)


class LoginRejected(Exception):
    """The node refused our callsign (e.g. the N0CALL placeholder)."""


class ClusterClient:
    def __init__(self, host: str, port: int, callsign: str,
                 on_spot, on_status, init_commands: list[str] | None = None) -> None:
        self.host, self.port, self.callsign = host, port, callsign
        self.on_spot = on_spot            # callable(Spot)
        self.on_status = on_status        # callable(str)  connected/disconnected/...
        # Enable the CW-skimmer (RBN) and FT8/FT4 feeds after login. CC Cluster
        # (VE7CC) requires these explicitly; nodes that don't know a command
        # just answer with an error line, which the spot parser ignores.
        self.init_commands = (init_commands if init_commands is not None
                              else ["SET/SKIMMER", "SET/FT8", "SET/FT4"])
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
                        for cmd in self.init_commands:
                            writer.write((cmd + "\r\n").encode())
                        await writer.drain()
                        sent_login = True
                        self.on_status(f"logged in as {self.callsign}"
                                       + (f" ({', '.join(self.init_commands)})"
                                          if self.init_commands else ""))
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        decoded = line.decode("utf-8", "ignore")
                        if sent_login and REJECTED.search(decoded):
                            self.on_status(
                                f"cluster rejected callsign {self.callsign} - "
                                "set your real callsign in SETUP")
                            raise LoginRejected
                        spot = parse_spot_line(decoded)
                        if spot:
                            self.on_spot(spot)
            except asyncio.CancelledError:
                return
            except LoginRejected:
                # No point hammering the node - the status message stays up and
                # fixing the callsign in SETUP recreates this client anyway.
                await asyncio.sleep(300)
            except Exception as exc:  # noqa: BLE001 - network errors of all kinds
                self.on_status(f"disconnected ({exc}); retrying in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
