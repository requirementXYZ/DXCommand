"""NCDXF/IARU International Beacon Project schedule (Faros heritage).

18 beacons rotate over 5 bands (14.100, 18.110, 21.150, 24.930, 28.200 MHz).
Each beacon transmits for 10 s per band, stepping up one band per slot; the
whole pattern repeats every 180 s. 4U1UN opens the cycle on 14.100 at
hh:mm:00 with mm divisible by 3.
"""
from __future__ import annotations

BEACONS = [  # (call, location, lat, lon) in schedule order
    ("4U1UN", "United Nations NY", 40.75, -73.97),
    ("VE8AT", "Inuvik, Canada", 68.32, -133.60),
    ("W6WX", "Mt Umunhum, CA", 37.15, -121.90),
    ("KH6RS", "Maui, Hawaii", 20.72, -156.45),
    ("ZL6B", "Masterton, NZ", -41.05, 175.60),
    ("VK6RBP", "Rolystone, Australia", -32.11, 116.05),
    ("JA2IGY", "Mt Asama, Japan", 34.45, 136.78),
    ("RR9O", "Novosibirsk, Russia", 54.98, 82.90),
    ("VR2B", "Hong Kong", 22.27, 114.15),
    ("4S7B", "Colombo, Sri Lanka", 6.90, 79.87),
    ("ZS6DN", "Pretoria, S. Africa", -25.90, 28.27),
    ("5Z4B", "Kilifi, Kenya", -3.62, 39.85),
    ("4X6TU", "Tel Aviv, Israel", 32.05, 34.77),
    ("OH2B", "Lohja, Finland", 60.32, 24.85),
    ("CS3B", "Madeira", 32.72, -16.88),
    ("LU4AA", "Buenos Aires", -34.62, -58.42),
    ("OA4B", "Lima, Peru", -12.07, -77.03),
    ("YV5B", "Caracas, Venezuela", 10.42, -66.85),
]

BANDS_KHZ = [14100.0, 18110.0, 21150.0, 24930.0, 28200.0]
SLOT_S = 10
CYCLE_S = SLOT_S * len(BEACONS)  # 180


def current_slot(utc_seconds: float) -> int:
    return int(utc_seconds % CYCLE_S) // SLOT_S


def transmitting_now(utc_seconds: float) -> list[dict]:
    """One entry per band: which beacon is on the air right now."""
    slot = current_slot(utc_seconds)
    out = []
    for band_i, freq in enumerate(BANDS_KHZ):
        beacon_i = (slot - band_i) % len(BEACONS)
        call, loc, lat, lon = BEACONS[beacon_i]
        out.append({
            "freq": freq, "call": call, "location": loc, "lat": lat, "lon": lon,
            "slot_remaining_s": SLOT_S - int(utc_seconds % SLOT_S),
        })
    return out
