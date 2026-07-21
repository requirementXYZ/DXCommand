"""Worked/confirmed DXCC tracking, persisted to data/worked.json.

State shape (v2): { entity_name: { band: { mode: "W" | "C" } } }
  "W" = worked, "C" = confirmed (QSL/LoTW received). Legacy v1 files stored
  { entity: { band: [modes...] } } and are migrated on load.

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

WORKED = "W"
CONFIRMED = "C"


class NeededTracker:
    def __init__(self, cty: CtyDatabase, path: Path) -> None:
        self.cty = cty
        self.path = path
        self.worked: dict[str, dict[str, dict[str, str]]] = {}
        if path.exists():
            try:
                self.worked = self._migrate(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                self.worked = {}

    @staticmethod
    def _migrate(data: dict) -> dict:
        """v1 stored mode lists; v2 stores {mode: status}."""
        out: dict = {}
        for entity, bands in data.items():
            out[entity] = {}
            for band, modes in bands.items():
                if isinstance(modes, list):
                    out[entity][band] = {m: WORKED for m in modes}
                else:
                    out[entity][band] = dict(modes)
        return out

    def save(self) -> None:
        self.path.write_text(json.dumps(self.worked, indent=1), encoding="utf-8")

    def _upgrade_slot(self, entity: str, band: str, mode: str, status: str) -> bool:
        """Record a slot; confirmations never downgrade. Returns True if changed."""
        slot = self.worked.setdefault(entity, {}).setdefault(band, {})
        if slot.get(mode) == CONFIRMED or slot.get(mode) == status:
            return False
        if slot.get(mode) == WORKED and status != CONFIRMED:
            return False
        slot[mode] = status
        return True

    def import_adif(self, text: str) -> dict:
        qsos = parse_adif(text)
        added = 0
        unresolved = 0
        for q in qsos:
            call, band, mode, confirmed = qso_summary(q)
            ent = self.cty.lookup(call)
            name = q.get("country") or (ent.name if ent else None)
            if not name or not band:
                unresolved += 1
                continue
            if self._upgrade_slot(name, band, mode,
                                  CONFIRMED if confirmed else WORKED):
                added += 1
        self.save()
        return {"qsos": len(qsos), "slots_added": added, "unresolved": unresolved,
                "entities": len(self.worked)}

    def record_qso(self, call: str, band: str, mode: str) -> None:
        ent = self.cty.lookup(call)
        if not ent or not band:
            return
        if self._upgrade_slot(ent.name, band, mode, WORKED):
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
        if band and mode and mode in ("CW", "FT8", "FT4") and mode not in bands.get(band, {}):
            return "mode"
        return ""

    def slot_status(self, entity: str, band: str, mode: str) -> str:
        """"" (needed) | "W" (worked) | "C" (confirmed) for an exact slot."""
        return self.worked.get(entity, {}).get(band, {}).get(mode, "")

    def entity_matrix(self, entity: str, bands: list[str], modes: list[str]) -> dict:
        return {b: {m: self.slot_status(entity, b, m) for m in modes} for b in bands}

    def stats(self) -> dict:
        slots = [s for b in self.worked.values() for m in b.values() for s in m.values()]
        return {"entities_worked": len(self.worked),
                "slots": len(slots),
                "confirmed_slots": sum(1 for s in slots if s == CONFIRMED)}
