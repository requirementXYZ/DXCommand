"""Worked/needed DXCC tracking, persisted to data/worked.json.

State shape: { entity_name: { band: [modes...] } }
Needed levels for a (entity, band, mode) slot:
  "atno"  - entity never worked at all
  "band"  - entity worked, but not on this band
  "mode"  - entity+band worked, but not in this mode
  ""      - fully worked slot
"""
from __future__ import annotations

import json
from pathlib import Path

from .adif import parse_adif, qso_summary
from .cty import CtyDatabase


class NeededTracker:
    def __init__(self, cty: CtyDatabase, path: Path) -> None:
        self.cty = cty
        self.path = path
        self.worked: dict[str, dict[str, list[str]]] = {}
        if path.exists():
            try:
                self.worked = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.worked = {}

    def save(self) -> None:
        self.path.write_text(json.dumps(self.worked, indent=1), encoding="utf-8")

    def import_adif(self, text: str) -> dict:
        qsos = parse_adif(text)
        added = 0
        unresolved = 0
        for q in qsos:
            call, band, mode, _confirmed = qso_summary(q)
            ent = self.cty.lookup(call)
            name = q.get("country") or (ent.name if ent else None)
            if not name or not band:
                unresolved += 1
                continue
            modes = self.worked.setdefault(name, {}).setdefault(band, [])
            if mode not in modes:
                modes.append(mode)
                added += 1
        self.save()
        return {"qsos": len(qsos), "slots_added": added, "unresolved": unresolved,
                "entities": len(self.worked)}

    def record_qso(self, call: str, band: str, mode: str) -> None:
        ent = self.cty.lookup(call)
        if not ent or not band:
            return
        modes = self.worked.setdefault(ent.name, {}).setdefault(band, [])
        if mode not in modes:
            modes.append(mode)
            self.save()

    def needed(self, call: str, band: str, mode: str) -> str:
        ent = self.cty.lookup(call)
        if not ent:
            return ""
        bands = self.worked.get(ent.name)
        if not bands:
            return "atno"
        if band and band not in bands:
            return "band"
        if band and mode and mode in ("CW", "FT8", "FT4") and mode not in bands.get(band, []):
            return "mode"
        return ""

    def stats(self) -> dict:
        return {"entities_worked": len(self.worked),
                "slots": sum(len(m) for b in self.worked.values() for m in b.values())}
