"""DX cluster spot parsing and band/mode classification."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict, field

# "DX de SPOTTER:    14025.0  DX0CALL      comment text            1234Z"
SPOT_RE = re.compile(
    r"^DX de\s+(?P<spotter>[A-Z0-9/\-#]+?):?\s+"
    r"(?P<freq>\d{3,6}(?:\.\d+)?)\s+"
    r"(?P<dx>[A-Z0-9/]+)\s*"
    r"(?P<comment>.*?)\s*"
    r"(?P<time>\d{4}Z)?\s*(?:<[A-Z]{2}\d{2}>)?\s*$",
    re.IGNORECASE,
)

BANDS = [  # (name, lo_khz, hi_khz)
    ("160m", 1800, 2000), ("80m", 3500, 4000), ("60m", 5250, 5450),
    ("40m", 7000, 7300), ("30m", 10100, 10150), ("20m", 14000, 14350),
    ("17m", 18068, 18168), ("15m", 21000, 21450), ("12m", 24890, 24990),
    ("10m", 28000, 29700), ("6m", 50000, 54000),
]

# Standard dial frequencies (kHz); a spot within +3.5 kHz above is in-window.
FT8_DIALS = [1840, 3573, 7074, 10136, 14074, 18100, 21074, 24915, 28074, 50313, 50323]
FT4_DIALS = [3575, 7047.5, 10140, 14080, 18104, 21140, 24919, 28180, 50318]

# Top of the CW-typical segment per band (kHz) - heuristic, not regulation.
CW_TOP = {"160m": 1840, "80m": 3570, "60m": 5354, "40m": 7040, "30m": 10130,
          "20m": 14070, "17m": 18095, "15m": 21070, "12m": 24915, "10m": 28070,
          "6m": 50100}

MODE_WORDS = [
    ("FT8", re.compile(r"\bFT-?8\b", re.I)),
    ("FT4", re.compile(r"\bFT-?4\b", re.I)),
    ("CW", re.compile(r"\bCW\b|\bQRQ\b|\bQRS\b|\b\d{1,2}\s?WPM\b", re.I)),
    ("RTTY", re.compile(r"\bRTTY\b", re.I)),
    ("SSB", re.compile(r"\bSSB\b|\bUSB\b|\bLSB\b", re.I)),
]

SPLIT_UP = re.compile(r"\b(UP|DN|DWN|DOWN)\s*(\d{1,3}(?:\.\d+)?)?\b", re.I)
QSX = re.compile(r"\bQSX\s*(\d{3,6}(?:\.\d+)?)\b", re.I)
SNR_RE = re.compile(r"\b(\d{1,2})\s?dB\b", re.I)   # RBN/skimmer comments


@dataclass
class Spot:
    dx_call: str
    freq: float                  # kHz
    spotter: str = ""
    comment: str = ""
    band: str = ""
    mode: str = "OTHER"
    ts: float = field(default_factory=time.time)
    split_tx_khz: float | None = None
    source: str = "cluster"
    dxcc: dict | None = None
    needed: str = ""             # "", "atno", "band", "mode"
    watched: bool = False
    snr: int | None = None       # dB, from RBN/skimmer comments
    spotters: list = field(default_factory=list)  # [{call, cont, snr, ts}]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.key()
        d["age_s"] = int(time.time() - self.ts)
        d["heard_conts"] = sorted({s.get("cont") for s in self.spotters
                                   if s.get("cont")})
        return d

    def key(self) -> str:
        return f"{self.dx_call}|{self.band}|{round(self.freq)}"


def band_for(freq_khz: float) -> str:
    for name, lo, hi in BANDS:
        if lo <= freq_khz <= hi:
            return name
    return ""


def classify_mode(freq_khz: float, comment: str) -> str:
    for mode, rx in MODE_WORDS:
        if rx.search(comment or ""):
            return mode
    for dial in FT8_DIALS:
        if dial - 0.5 <= freq_khz <= dial + 3.5:
            return "FT8"
    for dial in FT4_DIALS:
        if dial - 0.5 <= freq_khz <= dial + 3.5:
            return "FT4"
    band = band_for(freq_khz)
    if band and freq_khz <= CW_TOP.get(band, 0):
        return "CW"
    if band:
        return "SSB"
    return "OTHER"


def split_hint(freq_khz: float, comment: str) -> float | None:
    """Return TX frequency in kHz if the comment implies split."""
    m = QSX.search(comment or "")
    if m:
        qsx = float(m.group(1))
        if band_for(qsx):
            return qsx
    m = SPLIT_UP.search(comment or "")
    if m:
        amount = float(m.group(2)) if m.group(2) else 2.0  # bare "UP": assume 2
        if amount > 200:  # someone wrote a full frequency after UP
            return amount if band_for(amount) else None
        return freq_khz + amount if m.group(1).upper() == "UP" else freq_khz - amount
    return None


def parse_spot_line(line: str) -> Spot | None:
    m = SPOT_RE.match(line.strip())
    if not m:
        return None
    try:
        freq = float(m.group("freq"))
    except ValueError:
        return None
    band = band_for(freq)
    if not band:
        return None
    dx = m.group("dx").upper()
    if len(dx) < 3 or not any(c.isdigit() for c in dx):
        return None
    comment = (m.group("comment") or "").strip()
    snr_m = SNR_RE.search(comment)
    spotter = m.group("spotter").upper().rstrip("-#")
    spot = Spot(
        dx_call=dx,
        freq=freq,
        spotter=spotter,
        comment=comment,
        band=band,
        mode=classify_mode(freq, comment),
        split_tx_khz=split_hint(freq, comment),
        snr=int(snr_m.group(1)) if snr_m else None,
    )
    spot.spotters = [{"call": spotter, "cont": None, "snr": spot.snr,
                      "ts": spot.ts}]
    return spot
