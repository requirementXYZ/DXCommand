"""Minimal ADIF (.adi) parser - extracts the fields needed for DXCC tracking."""
from __future__ import annotations

import re

FIELD_RE = re.compile(r"<(\w+)(?::(\d+))(?::[A-Za-z])?>", re.S)

# ADIF mode -> dashboard mode group
MODE_GROUP = {
    "CW": "CW", "FT8": "FT8", "FT4": "FT4", "MFSK": "FT4",
    "SSB": "SSB", "USB": "SSB", "LSB": "SSB", "RTTY": "RTTY",
}


def parse_adif(text: str) -> list[dict]:
    """Return a list of QSO dicts with lowercase keys."""
    # Skip header: records start after <EOH> if present
    m = re.search(r"<eoh>", text, re.I)
    body = text[m.end():] if m else text
    qsos: list[dict] = []
    for rec in re.split(r"<eor>", body, flags=re.I):
        fields: dict[str, str] = {}
        pos = 0
        while True:
            fm = FIELD_RE.search(rec, pos)
            if not fm:
                break
            name = fm.group(1).lower()
            length = int(fm.group(2))
            start = fm.end()
            fields[name] = rec[start:start + length].strip()
            pos = start + length
        if fields.get("call"):
            qsos.append(fields)
    return qsos


def qso_summary(fields: dict) -> tuple[str, str, str, bool]:
    """(call, band, mode_group, confirmed) from an ADIF record."""
    call = fields.get("call", "").upper()
    band = fields.get("band", "").lower()
    mode = MODE_GROUP.get(fields.get("mode", "").upper(),
                          fields.get("mode", "").upper() or "OTHER")
    if fields.get("submode", "").upper() == "FT4":
        mode = "FT4"
    confirmed = (fields.get("qsl_rcvd", "").upper() == "Y"
                 or fields.get("lotw_qsl_rcvd", "").upper() == "Y")
    return call, band, mode, confirmed
