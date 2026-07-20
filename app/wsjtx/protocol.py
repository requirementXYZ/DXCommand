"""WSJT-X UDP message protocol (QDataStream wire format).

Reference: WSJT-X source NetworkMessage.hpp (same protocol VE3NEA's WsjtxUtils
implements). Big-endian; strings are u32 length-prefixed utf-8 (0xFFFFFFFF = null).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = 0xADBCCBDA
SCHEMA = 2

HEARTBEAT, STATUS, DECODE, CLEAR, REPLY, QSO_LOGGED, CLOSE = 0, 1, 2, 3, 4, 5, 6


class Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def _take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise ValueError("short packet")
        b = self.data[self.pos:self.pos + n]
        self.pos += n
        return b

    def u8(self) -> int:
        return self._take(1)[0]

    def bool(self) -> bool:
        return self.u8() != 0

    def u32(self) -> int:
        return struct.unpack(">I", self._take(4))[0]

    def i32(self) -> int:
        return struct.unpack(">i", self._take(4))[0]

    def u64(self) -> int:
        return struct.unpack(">Q", self._take(8))[0]

    def f64(self) -> float:
        return struct.unpack(">d", self._take(8))[0]

    def utf8(self) -> str:
        n = self.u32()
        if n == 0xFFFFFFFF:
            return ""
        return self._take(n).decode("utf-8", "replace")

    @property
    def remaining(self) -> int:
        return len(self.data) - self.pos


class Writer:
    def __init__(self) -> None:
        self.buf = bytearray()

    def u8(self, v: int):  self.buf += struct.pack(">B", v); return self
    def bool_(self, v: bool): return self.u8(1 if v else 0)
    def u32(self, v: int): self.buf += struct.pack(">I", v); return self
    def i32(self, v: int): self.buf += struct.pack(">i", v); return self
    def f64(self, v: float): self.buf += struct.pack(">d", v); return self

    def utf8(self, s: str | None):
        if s is None:
            return self.u32(0xFFFFFFFF)
        b = s.encode("utf-8")
        self.u32(len(b))
        self.buf += b
        return self

    def bytes(self) -> bytes:
        return bytes(self.buf)


@dataclass
class Decode:
    client_id: str
    is_new: bool
    time_ms: int          # ms since UTC midnight
    snr: int
    delta_t: float
    delta_f: int
    mode: str
    message: str
    low_confidence: bool = False
    off_air: bool = False


@dataclass
class Status:
    client_id: str
    dial_freq: int        # Hz
    mode: str
    dx_call: str
    tx_enabled: bool = False
    transmitting: bool = False
    decoding: bool = False
    de_call: str = ""
    de_grid: str = ""
    dx_grid: str = ""


@dataclass
class QsoLogged:
    client_id: str
    dx_call: str
    dx_grid: str
    tx_freq: int
    mode: str
    report_sent: str
    report_recv: str


def parse_packet(data: bytes):
    """Return Decode | Status | QsoLogged | ('heartbeat', id) | None."""
    r = Reader(data)
    if r.u32() != MAGIC:
        return None
    r.u32()  # schema
    msg_type = r.u32()
    cid = r.utf8()
    if msg_type == HEARTBEAT:
        return ("heartbeat", cid)
    if msg_type == DECODE:
        return Decode(cid, r.bool(), r.u32(), r.i32(), r.f64(), r.u32(),
                      r.utf8(), r.utf8(),
                      r.bool() if r.remaining else False,
                      r.bool() if r.remaining else False)
    if msg_type == STATUS:
        dial = r.u64()
        mode = r.utf8()
        dx_call = r.utf8()
        r.utf8()  # report
        r.utf8()  # tx mode
        tx_enabled = r.bool()
        transmitting = r.bool()
        decoding = r.bool()
        r.u32()   # rx df
        r.u32()   # tx df
        de_call = r.utf8() if r.remaining else ""
        de_grid = r.utf8() if r.remaining else ""
        dx_grid = r.utf8() if r.remaining else ""
        return Status(cid, dial, mode, dx_call, tx_enabled, transmitting,
                      decoding, de_call, de_grid, dx_grid)
    if msg_type == QSO_LOGGED:
        # id, QDateTime time_off (julian u64 + ms u32 + spec u8), dx call, grid,
        # tx freq u64, mode, report sent, report recv ...
        r.u64(); r.u32(); r.u8()
        dx_call = r.utf8()
        dx_grid = r.utf8()
        tx_freq = r.u64()
        mode = r.utf8()
        sent = r.utf8()
        recv = r.utf8()
        return QsoLogged(cid, dx_call, dx_grid, tx_freq, mode, sent, recv)
    return None


def encode_reply(d: Decode, modifiers: int = 0) -> bytes:
    """Reply packet: tells WSJT-X to respond to this decode."""
    w = Writer()
    w.u32(MAGIC).u32(SCHEMA).u32(REPLY)
    w.utf8(d.client_id)
    w.u32(d.time_ms).i32(d.snr).f64(d.delta_t).u32(d.delta_f)
    w.utf8(d.mode).utf8(d.message)
    w.bool_(d.low_confidence).u8(modifiers)
    return w.bytes()


def encode_heartbeat(client_id: str = "DXCommand") -> bytes:
    w = Writer()
    w.u32(MAGIC).u32(SCHEMA).u32(HEARTBEAT)
    w.utf8(client_id).u32(3).utf8("2.6.1").utf8("")
    return w.bytes()


def encode_decode(d: Decode) -> bytes:
    """Used by the simulator and tests."""
    w = Writer()
    w.u32(MAGIC).u32(SCHEMA).u32(DECODE)
    w.utf8(d.client_id)
    w.bool_(d.is_new).u32(d.time_ms).i32(d.snr).f64(d.delta_t).u32(d.delta_f)
    w.utf8(d.mode).utf8(d.message).bool_(d.low_confidence).bool_(d.off_air)
    return w.bytes()


def encode_status(s: Status) -> bytes:
    w = Writer()
    w.u32(MAGIC).u32(SCHEMA).u32(STATUS)
    w.utf8(s.client_id)
    w.buf += struct.pack(">Q", s.dial_freq)
    w.utf8(s.mode).utf8(s.dx_call).utf8("-10").utf8(s.mode)
    w.bool_(s.tx_enabled).bool_(s.transmitting).bool_(s.decoding)
    w.u32(1200).u32(1500)
    w.utf8(s.de_call).utf8(s.de_grid).utf8(s.dx_grid)
    return w.bytes()
