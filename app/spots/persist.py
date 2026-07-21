"""SQLite spot-event history: survives restarts, feeds activity timelines.

Every incoming spot line is recorded as an event (refreshes included), which
is what a per-DX activity timeline needs. Volume is tiny by DB standards
(RBN worst case a few events/second), so synchronous writes on the event
loop are fine.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS spot_events (
    ts      REAL NOT NULL,
    dx_call TEXT NOT NULL,
    freq    REAL NOT NULL,
    band    TEXT NOT NULL,
    mode    TEXT NOT NULL,
    snr     INTEGER,
    spotter TEXT,
    source  TEXT,
    comment TEXT,
    split_tx REAL
);
CREATE INDEX IF NOT EXISTS idx_events_call_ts ON spot_events (dx_call, ts);
CREATE INDEX IF NOT EXISTS idx_events_ts ON spot_events (ts);
"""

KEEP_DAYS = 7


class SpotDB:
    def __init__(self, path: Path) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()
        self._last_prune = time.time()
        self.prune()   # startup cleanup; record() re-prunes hourly

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def record(self, spot) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO spot_events VALUES (?,?,?,?,?,?,?,?,?,?)",
                (spot.ts, spot.dx_call, spot.freq, spot.band, spot.mode,
                 spot.snr, spot.spotter, spot.source, spot.comment,
                 spot.split_tx_khz))
            self._conn.commit()
        now = time.time()
        if now - self._last_prune > 3600:
            self._last_prune = now
            self.prune()

    def prune(self, keep_days: int = KEEP_DAYS) -> int:
        cutoff = time.time() - keep_days * 86400
        with self._lock:
            cur = self._conn.execute("DELETE FROM spot_events WHERE ts < ?", (cutoff,))
            self._conn.commit()
        return cur.rowcount

    def recent(self, seconds: int) -> list[dict]:
        """Latest event per (call, band) within the window - for store seeding."""
        cutoff = time.time() - seconds
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, dx_call, freq, band, mode, snr, spotter, source, "
                "comment, split_tx FROM spot_events WHERE ts >= ? ORDER BY ts",
                (cutoff,)).fetchall()
        return [dict(zip(("ts", "dx_call", "freq", "band", "mode", "snr",
                          "spotter", "source", "comment", "split_tx"), r))
                for r in rows]

    def timeline(self, dx_call: str, hours: int = 24) -> list[dict]:
        """Hourly activity buckets per band for one callsign."""
        cutoff = time.time() - hours * 3600
        with self._lock:
            rows = self._conn.execute(
                "SELECT band, mode, CAST(ts / 3600 AS INTEGER) AS hour_bucket, "
                "COUNT(*), MAX(ts) FROM spot_events "
                "WHERE dx_call = ? AND ts >= ? GROUP BY band, mode, hour_bucket",
                (dx_call.upper(), cutoff)).fetchall()
        return [{"band": b, "mode": m, "hour_ts": hb * 3600, "count": c,
                 "last_ts": last} for b, m, hb, c, last in rows]

    def activity_summary(self, dx_call: str, window_s: int = 86400) -> list[dict]:
        """Per band+mode: count, last heard, last frequency (for the slot matrix)."""
        cutoff = time.time() - window_s
        with self._lock:
            rows = self._conn.execute(
                "SELECT band, mode, COUNT(*), MAX(ts) FROM spot_events "
                "WHERE dx_call = ? AND ts >= ? GROUP BY band, mode",
                (dx_call.upper(), cutoff)).fetchall()
            out = []
            for band, mode, count, last_ts in rows:
                freq_row = self._conn.execute(
                    "SELECT freq, split_tx FROM spot_events WHERE dx_call = ? "
                    "AND band = ? AND mode = ? ORDER BY ts DESC LIMIT 1",
                    (dx_call.upper(), band, mode)).fetchone()
                out.append({"band": band, "mode": mode, "count": count,
                            "last_ts": last_ts, "last_freq": freq_row[0],
                            "split_tx": freq_row[1]})
        return out
