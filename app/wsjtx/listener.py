"""WSJT-X UDP listener + reply sender."""
from __future__ import annotations

import asyncio

from .protocol import (Decode, QsoLogged, Status, encode_reply, parse_packet)


class _Proto(asyncio.DatagramProtocol):
    def __init__(self, service: "WsjtxService") -> None:
        self.service = service

    def datagram_received(self, data: bytes, addr) -> None:
        try:
            msg = parse_packet(data)
        except ValueError:
            return
        if msg is None:
            return
        self.service.last_addr = addr
        if isinstance(msg, Decode):
            self.service.decodes[self._decode_key(msg)] = msg
            if len(self.service.decodes) > 400:
                self.service.decodes.pop(next(iter(self.service.decodes)))
            self.service.on_decode(msg)
        elif isinstance(msg, Status):
            self.service.on_status(msg)
        elif isinstance(msg, QsoLogged):
            self.service.on_qso(msg)
        elif isinstance(msg, tuple) and msg[0] == "heartbeat":
            self.service.on_heartbeat(msg[1])

    @staticmethod
    def _decode_key(d: Decode) -> str:
        return f"{d.time_ms}|{d.delta_f}|{d.message}"


class WsjtxService:
    def __init__(self, port: int, on_decode, on_status, on_qso, on_heartbeat) -> None:
        self.port = port
        self.on_decode = on_decode
        self.on_status = on_status
        self.on_qso = on_qso
        self.on_heartbeat = on_heartbeat
        self.last_addr = None
        self.decodes: dict[str, Decode] = {}
        self._transport = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            self._transport, _ = await loop.create_datagram_endpoint(
                lambda: _Proto(self), local_addr=("0.0.0.0", self.port))
            print(f"[wsjtx] listening on UDP {self.port}")
        except OSError as exc:
            print(f"[wsjtx] cannot bind UDP {self.port}: {exc}")

    async def stop(self) -> None:
        if self._transport:
            self._transport.close()

    def reply_to(self, decode_key: str) -> bool:
        """Send a Reply for a stored decode -> WSJT-X starts calling that station."""
        d = self.decodes.get(decode_key)
        if not d or not self._transport or not self.last_addr:
            return False
        self._transport.sendto(encode_reply(d), self.last_addr)
        return True
