from app.wsjtx.protocol import (Decode, Status, encode_decode, encode_heartbeat,
                                encode_reply, encode_status, parse_packet,
                                MAGIC, REPLY)
from app.wsjtx.protocol import Reader


def test_decode_roundtrip():
    d = Decode(client_id="WSJT-X", is_new=True, time_ms=45_015_000, snr=-14,
               delta_t=0.2, delta_f=1520, mode="~", message="CQ 3Y0K JD59")
    parsed = parse_packet(encode_decode(d))
    assert isinstance(parsed, Decode)
    assert parsed.message == "CQ 3Y0K JD59"
    assert parsed.snr == -14
    assert parsed.delta_f == 1520
    assert abs(parsed.delta_t - 0.2) < 1e-9


def test_status_roundtrip():
    s = Status(client_id="WSJT-X", dial_freq=14_090_000, mode="FT8",
               dx_call="3Y0K", de_call="N0CALL", de_grid="FN31", dx_grid="JD59")
    parsed = parse_packet(encode_status(s))
    assert isinstance(parsed, Status)
    assert parsed.dial_freq == 14_090_000
    assert parsed.dx_call == "3Y0K"
    assert parsed.de_grid == "FN31"


def test_reply_encoding():
    d = Decode(client_id="WSJT-X", is_new=True, time_ms=1000, snr=-5,
               delta_t=0.0, delta_f=800, mode="~", message="CQ K1ABC FN42")
    pkt = encode_reply(d)
    r = Reader(pkt)
    assert r.u32() == MAGIC
    r.u32()
    assert r.u32() == REPLY
    assert r.utf8() == "WSJT-X"
    assert r.u32() == 1000


def test_heartbeat_parses():
    parsed = parse_packet(encode_heartbeat("abc"))
    assert parsed == ("heartbeat", "abc")


def test_garbage_rejected():
    assert parse_packet(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08") is None
