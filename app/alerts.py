"""Alert engine: decides which spots/decodes deserve a notification.

Configured via the "alerts" block in config.json (editable from the UI):
  enabled, notify_atno, notify_band, notify_mode, notify_watch,
  only_my_continent (only alert when a spotter on your continent hears them),
  quiet ("HH:MM-HH:MM" local time, empty = never quiet), sound ("ping"|"alarm"|"off").

Emits "alert" frames on the event bus; the browser turns them into desktop
notifications and sounds. Keeps a ring log so missed alerts can be reviewed.
"""
from __future__ import annotations

import time
from collections import deque
from datetime import datetime

DEDUPE_S = 600  # same call+band+reason at most once per 10 min


class AlertEngine:
    def __init__(self, get_cfg, my_continent: str, publish) -> None:
        self._get_cfg = get_cfg          # callable -> alerts config dict
        self.my_continent = my_continent
        self.publish = publish           # callable(frame_dict)
        self.log: deque = deque(maxlen=100)
        self._recent: dict[str, float] = {}

    # -- helpers ------------------------------------------------------------
    @property
    def cfg(self) -> dict:
        return self._get_cfg()

    def in_quiet_hours(self, now: datetime | None = None) -> bool:
        quiet = (self.cfg.get("quiet") or "").strip()
        if "-" not in quiet:
            return False
        try:
            start_s, end_s = quiet.split("-")
            now = now or datetime.now()
            cur = now.hour * 60 + now.minute
            sh, sm = (int(x) for x in start_s.strip().split(":"))
            eh, em = (int(x) for x in end_s.strip().split(":"))
            start, end = sh * 60 + sm, eh * 60 + em
        except ValueError:
            return False
        if start == end:
            return False
        if start < end:
            return start <= cur < end
        return cur >= start or cur < end   # overnight window e.g. 22:00-07:00

    def _deduped(self, key: str, now: float) -> bool:
        last = self._recent.get(key)
        if last and now - last < DEDUPE_S:
            return True
        self._recent[key] = now
        if len(self._recent) > 500:
            cutoff = now - DEDUPE_S
            self._recent = {k: t for k, t in self._recent.items() if t >= cutoff}
        return False

    def _reason(self, needed: str, watched: bool) -> str | None:
        c = self.cfg
        if watched and c.get("notify_watch", True):
            return "watch"
        if needed == "atno" and c.get("notify_atno", True):
            return "atno"
        if needed == "band" and c.get("notify_band", False):
            return "band"
        if needed == "mode" and c.get("notify_mode", False):
            return "mode"
        return None

    # -- entry points -------------------------------------------------------
    def check_spot(self, spot) -> None:
        """spot: app.spots.parser.Spot (already enriched)."""
        if not self.cfg.get("enabled", True) or self.in_quiet_hours():
            return
        reason = self._reason(spot.needed, spot.watched)
        if not reason:
            return
        if self.cfg.get("only_my_continent") and reason != "watch":
            conts = {sp.get("cont") for sp in (spot.spotters or [])}
            if self.my_continent not in conts:
                return
        now = time.time()
        if self._deduped(f"{spot.dx_call}|{spot.band}|{reason}", now):
            return
        self._emit({
            "reason": reason, "kind": "spot", "call": spot.dx_call,
            "freq": spot.freq, "band": spot.band, "mode": spot.mode,
            "split_tx_khz": spot.split_tx_khz,
            "entity": spot.dxcc["name"] if spot.dxcc else None,
            "text": self._text(reason, spot.dx_call, spot.band, spot.mode,
                               spot.dxcc["name"] if spot.dxcc else None),
            "ts": int(now),
        })

    def check_decode(self, frame: dict) -> None:
        """frame: the wsjtx_decode bus frame (has call/needed/watched)."""
        if not self.cfg.get("enabled", True) or self.in_quiet_hours():
            return
        call = frame.get("call")
        if not call:
            return
        reason = self._reason(frame.get("needed", ""), frame.get("watched", False))
        if not reason:
            return
        now = time.time()
        if self._deduped(f"{call}|FT8|{reason}", now):
            return
        self._emit({
            "reason": reason, "kind": "ft8", "call": call,
            "freq": None, "band": "", "mode": "FT8",
            "entity": frame.get("entity"),
            "text": self._text(reason, call, "", "FT8", frame.get("entity")),
            "ts": int(now),
        })

    @staticmethod
    def _text(reason: str, call: str, band: str, mode: str, entity: str | None) -> str:
        why = {"watch": "watch list", "atno": "ALL-TIME NEW ONE",
               "band": "new band", "mode": "new mode"}[reason]
        where = f" on {band}" if band else ""
        ent = f" ({entity})" if entity else ""
        return f"{call}{ent} {mode}{where} — {why}"

    def _emit(self, frame: dict) -> None:
        frame["sound"] = self.cfg.get("sound", "ping")
        self.log.appendleft(frame)
        self.publish(frame)
