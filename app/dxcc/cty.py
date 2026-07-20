"""cty.dat (AD1C country file) parser and callsign -> DXCC entity resolver.

Format reference: https://www.country-files.com/cty-dat-format/
  Country Name: CQ: ITU: Continent: Lat: Lon: TZ: PrimaryPrefix:
      prefix,prefix,=EXACTCALL,prefix(cq)[itu];
Longitude in cty.dat is positive WEST; we store the conventional sign (east+).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict
from pathlib import Path

CTY_URL = "https://www.country-files.com/cty/cty.dat"


@dataclass
class Entity:
    name: str
    prefix: str      # primary prefix
    cont: str
    cqz: int
    ituz: int
    lat: float
    lon: float       # east-positive

    def to_dict(self) -> dict:
        return asdict(self)


_OVERRIDE_RE = re.compile(r"\((\d+)\)|\[(\d+)\]|<([\d.+-]+)/([\d.+-]+)>|\{(\w+)\}|~[\d.+-]+~")


class CtyDatabase:
    def __init__(self) -> None:
        self.entities: list[Entity] = []
        self.prefix_map: dict[str, int] = {}   # prefix -> entity index
        self.exact_map: dict[str, int] = {}    # exact callsign -> entity index
        self._cache: dict[str, Entity | None] = {}
        self.source = ""                       # file the database was loaded from

    @classmethod
    def from_file(cls, path: Path) -> "CtyDatabase":
        db = cls()
        db._parse(path.read_text(encoding="utf-8", errors="replace"))
        return db

    def _parse(self, text: str) -> None:
        # Records are ';'-terminated; header fields are ':'-separated.
        for record in text.split(";"):
            record = record.strip()
            if not record:
                continue
            parts = record.split(":")
            if len(parts) < 9:
                continue
            try:
                name = parts[0].strip()
                cqz = int(parts[1])
                ituz = int(parts[2])
                cont = parts[3].strip()
                lat = float(parts[4])
                lon = -float(parts[5])  # cty.dat is west-positive
                primary = parts[7].strip().lstrip("*")
            except ValueError:
                continue
            idx = len(self.entities)
            self.entities.append(Entity(name, primary, cont, cqz, ituz, lat, lon))
            for alias in parts[8].replace("\r", "").replace("\n", "").split(","):
                alias = _OVERRIDE_RE.sub("", alias).strip().upper()
                if not alias:
                    continue
                if alias.startswith("="):
                    self.exact_map[alias[1:]] = idx
                else:
                    self.prefix_map[alias] = idx

    def lookup(self, call: str) -> Entity | None:
        call = call.upper().strip()
        if call in self._cache:
            return self._cache[call]
        ent = self._lookup(call)
        self._cache[call] = ent
        return ent

    def _lookup(self, call: str) -> Entity | None:
        if call in self.exact_map:
            return self.entities[self.exact_map[call]]
        base = self._base_call(call)
        if base in self.exact_map:
            return self.entities[self.exact_map[base]]
        for i in range(len(base), 0, -1):
            idx = self.prefix_map.get(base[:i])
            if idx is not None:
                return self.entities[idx]
        return None

    @staticmethod
    def _base_call(call: str) -> str:
        """Pick the DXCC-determining part of a portable call like K5D/HR9 or F/G3XYZ."""
        parts = call.split("/")
        if len(parts) == 1:
            return call
        # Drop pure suffix designators
        parts = [p for p in parts if p not in ("P", "M", "MM", "AM", "QRP", "A")
                 and not (len(p) == 1 and p.isdigit())]
        if not parts:
            return call
        # The prefix-like part is usually the shorter one; ties -> first.
        return min(parts, key=len)


def bearing_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[int, int]:
    """Short-path (azimuth deg, distance km)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    az = (math.degrees(math.atan2(y, x)) + 360) % 360
    d = math.acos(max(-1, min(1, math.sin(p1) * math.sin(p2) +
                              math.cos(p1) * math.cos(p2) * math.cos(dl)))) * 6371
    return round(az), round(d)


def load_database(data_dir: Path, bundled_dir: Path, offline: bool) -> CtyDatabase:
    """Prefer cached full cty.dat; try download when online; fall back to bundled."""
    cached = data_dir / "cty.dat"
    if not cached.exists() and not offline:
        try:
            import httpx
            r = httpx.get(CTY_URL, timeout=20, follow_redirects=True)
            r.raise_for_status()
            cached.write_text(r.text, encoding="utf-8")
            print(f"[dxcc] downloaded cty.dat ({len(r.text)//1024} kB)")
        except Exception as exc:  # noqa: BLE001
            print(f"[dxcc] cty.dat download failed ({exc}); using bundled subset")
    src = cached if cached.exists() else bundled_dir / "cty_builtin.dat"
    db = CtyDatabase.from_file(src)
    db.source = src.name
    print(f"[dxcc] {len(db.entities)} entities from {src.name}")
    return db
