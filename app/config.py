"""Configuration loading with sensible defaults and demo-mode override."""
from __future__ import annotations

import copy
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller onefile: assets unpack to _MEIPASS; config/data live next
    # to the exe so they survive between runs.
    ROOT = Path(sys.executable).resolve().parent
    ASSETS = Path(getattr(sys, "_MEIPASS", ROOT))
else:
    ROOT = Path(__file__).resolve().parent.parent
    ASSETS = ROOT
DATA_DIR = ROOT / "data"
STATIC_DIR = ASSETS / "static"
BUNDLED_DIR = ASSETS / "app" / "bundled"
CONFIG_PATH = ROOT / "config.json"

DEFAULTS: dict = {
    "callsign": "N0CALL",
    "grid": "IO95rj",
    "port": 8073,
    "demo_mode": False,
    "rig": {"backend": "omnirig", "rig_number": 1, "poll_ms": 300},
    "cluster": {
        "host": "dxc.ve7cc.net",
        "port": 23,
        "keep_modes": ["CW", "FT8", "FT4"],
        "init_commands": ["SET/SKIMMER", "SET/FT8", "SET/FT4"],
        "simulate": False,
    },
    "wsjtx": {"enabled": True, "udp_port": 2237, "simulate": False},
    "rbn": {"enabled": True, "host": "telnet.reversebeacon.net", "port": 7000},
    "spots": {"max_age_min": 30, "max_count": 2000},
    "alerts": {
        "enabled": True,
        "notify_atno": True,
        "notify_band": False,
        "notify_mode": False,
        "notify_watch": True,
        "only_my_continent": False,
        "quiet": "",
        "sound": "ping",
    },
    "logsync": {"paths": [], "auto_wsjtx": True, "poll_s": 30},
    "watch_list": [],
    "offline": False,
}


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            out[k] = _merge(base[k], v)
        else:
            out[k] = v
    return out


@dataclass
class Config:
    raw: dict = field(default_factory=lambda: dict(DEFAULTS))

    @property
    def callsign(self) -> str:
        return str(self.raw["callsign"]).upper()

    @property
    def grid(self) -> str:
        return self.raw["grid"]

    @property
    def port(self) -> int:
        return int(self.raw["port"])

    @property
    def demo_mode(self) -> bool:
        return bool(self.raw["demo_mode"])

    @property
    def offline(self) -> bool:
        return bool(self.raw["offline"]) or self.demo_mode

    def __getitem__(self, key: str):
        return self.raw[key]


def load_config(path: Path = CONFIG_PATH) -> Config:
    raw = copy.deepcopy(DEFAULTS)
    if path.exists():
        try:
            raw = _merge(raw, json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[config] failed to read {path}: {exc}; using defaults")
    if os.environ.get("DXDASH_DEMO") == "1":
        raw["demo_mode"] = True
    if raw.get("demo_mode"):
        raw["rig"]["backend"] = "simulator"
        raw["cluster"]["simulate"] = True
        raw["wsjtx"]["simulate"] = True
    DATA_DIR.mkdir(exist_ok=True)
    return Config(raw)


def save_config(raw: dict, path: Path = CONFIG_PATH) -> None:
    """Persist user-facing settings (only known top-level keys)."""
    persist = {k: raw[k] for k in DEFAULTS if k in raw}
    path.write_text(json.dumps(persist, indent=2), encoding="utf-8")


def update_config_file(path: Path = CONFIG_PATH, **fields) -> None:
    """Patch individual keys in config.json without persisting runtime state.

    Used for incidental saves (e.g. watch list) so a demo-forced session never
    overwrites the user's rig/cluster choices on disk.
    """
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        current = {}
    current.update(fields)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")


def grid_to_latlon(grid: str) -> tuple[float, float]:
    """Maidenhead grid square -> (lat, lon) of square center."""
    g = grid.strip().upper()
    if len(g) < 4:
        g = (g + "LL55LL")[:6]
    lon = (ord(g[0]) - ord("A")) * 20 - 180
    lat = (ord(g[1]) - ord("A")) * 10 - 90
    lon += int(g[2]) * 2
    lat += int(g[3]) * 1
    if len(g) >= 6 and g[4].isalpha() and g[5].isalpha():
        lon += (ord(g[4]) - ord("A")) * (2 / 24) + (1 / 24)
        lat += (ord(g[5]) - ord("A")) * (1 / 24) + (0.5 / 24)
    else:
        lon += 1
        lat += 0.5
    return lat, lon
