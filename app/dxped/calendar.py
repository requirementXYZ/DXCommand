"""DXpedition calendar (DX Bulletin Reader heritage).

Priority: user-maintained data/dxpeditions.json > live NG3K ADXO fetch >
bundled sample. The NG3K page is HTML meant for humans; we parse it
defensively and fall back rather than fail.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

NG3K_URL = "https://www.ng3k.com/misc/adxo.html"


def _from_ng3k(html: str) -> list[dict]:
    items: list[dict] = []
    # ADXO rows carry the operation callsign in a link and dates in cells.
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        cells = [re.sub(r"<[^>]+>", " ", c).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        if len(cells) < 4:
            continue
        text = " ".join(cells)
        call_m = re.search(r"\b([A-Z0-9]{1,4}\d[A-Z0-9/]*[A-Z])\b", text)
        date_m = re.findall(r"\b(20\d\d\s?[A-Z][a-z]{2}\s?\d{1,2})\b", text)
        if call_m and len(date_m) >= 2:
            items.append({"callsign": call_m.group(1), "entity": cells[2][:40],
                          "start": date_m[0], "end": date_m[1],
                          "bands": "", "modes": "", "info": "NG3K ADXO"})
    return items[:40]


async def load_dxpeditions(data_dir: Path, bundled_dir: Path, offline: bool) -> dict:
    user_file = data_dir / "dxpeditions.json"
    if user_file.exists():
        try:
            return json.loads(user_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    if not offline:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                r = await client.get(NG3K_URL)
                r.raise_for_status()
            items = _from_ng3k(r.text)
            if items:
                return {"source": "NG3K ADXO (live)", "items": items}
        except Exception as exc:  # noqa: BLE001
            print(f"[dxped] NG3K fetch failed: {exc}")
    return json.loads((bundled_dir / "dxpeditions_sample.json")
                      .read_text(encoding="utf-8"))
