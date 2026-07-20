"""Solar/geomagnetic indices from hamqsl.com (N0NBH), with demo fallback."""
from __future__ import annotations

import asyncio
import re
import time

SOLAR_URL = "https://www.hamqsl.com/solarxml.php"
REFRESH_S = 1800

DEMO_DATA = {
    "sfi": 168, "sunspots": 112, "a_index": 6, "k_index": 2, "xray": "B7.4",
    "aurora": 2, "updated": "demo data",
    "bands": [
        {"name": "80m-40m", "day": "Fair", "night": "Good"},
        {"name": "30m-20m", "day": "Good", "night": "Good"},
        {"name": "17m-15m", "day": "Good", "night": "Fair"},
        {"name": "12m-10m", "day": "Fair", "night": "Poor"},
    ],
    "source": "simulated",
}


def _tag(xml: str, name: str) -> str:
    m = re.search(rf"<{name}[^>]*>\s*(.*?)\s*</{name}>", xml, re.S)
    return m.group(1) if m else ""


def parse_solar_xml(xml: str) -> dict:
    def num(name, cast=int, default=0):
        try:
            return cast(_tag(xml, name))
        except (ValueError, TypeError):
            return default

    bands = []
    for m in re.finditer(
            r'<band name="([^"]+)" time="(day|night)">\s*([^<]*?)\s*</band>', xml):
        name, when, cond = m.group(1), m.group(2), m.group(3)
        entry = next((b for b in bands if b["name"] == name), None)
        if not entry:
            entry = {"name": name, "day": "?", "night": "?"}
            bands.append(entry)
        entry[when] = cond
    return {
        "sfi": num("solarflux"), "sunspots": num("sunspots"),
        "a_index": num("aindex"), "k_index": num("kindex"),
        "xray": _tag(xml, "xray"), "aurora": num("aurora"),
        "updated": _tag(xml, "updated"), "bands": bands, "source": "hamqsl.com",
    }


class SolarService:
    def __init__(self, offline: bool, on_update) -> None:
        self.offline = offline
        self.on_update = on_update
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="solar")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _run(self) -> None:
        while True:
            data = DEMO_DATA
            if not self.offline:
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=20) as client:
                        r = await client.get(SOLAR_URL)
                        r.raise_for_status()
                        data = parse_solar_xml(r.text)
                except Exception as exc:  # noqa: BLE001
                    data = {**DEMO_DATA, "source": f"unavailable ({exc})"}
            data["fetched_at"] = int(time.time())
            self.on_update(data)
            try:
                await asyncio.sleep(REFRESH_S)
            except asyncio.CancelledError:
                return
