import time

import pytest

from app.spots.parser import Spot
from app.spots.persist import SpotDB


@pytest.fixture()
def db(tmp_path) -> SpotDB:
    d = SpotDB(tmp_path / "spots.db")
    yield d
    d.close()


def make(call="3Y0K", freq=14023.0, band="20m", mode="CW", ts=None, snr=None):
    return Spot(dx_call=call, freq=freq, band=band, mode=mode,
                ts=ts if ts is not None else time.time(),
                spotter="W3LPL", comment="UP 2", snr=snr, split_tx_khz=14025.0)


def test_record_and_recent(db):
    db.record(make())
    db.record(make(call="JA1NUT", freq=14012.0))
    rows = db.recent(60)
    assert len(rows) == 2
    assert rows[0]["dx_call"] == "3Y0K"
    assert rows[0]["split_tx"] == 14025.0


def test_recent_window_excludes_old(db):
    db.record(make(ts=time.time() - 7200))
    db.record(make(call="JA1NUT"))
    assert [r["dx_call"] for r in db.recent(3600)] == ["JA1NUT"]


def test_activity_summary_groups_band_mode(db):
    now = time.time()
    for i in range(3):
        db.record(make(ts=now - i * 60))
    db.record(make(freq=14090.0, mode="FT8", ts=now))
    acts = {(a["band"], a["mode"]): a for a in db.activity_summary("3Y0K")}
    assert acts[("20m", "CW")]["count"] == 3
    assert acts[("20m", "FT8")]["last_freq"] == 14090.0


def test_timeline_buckets(db):
    now = time.time()
    db.record(make(ts=now))
    db.record(make(ts=now - 3700))          # previous hour bucket
    tl = db.timeline("3Y0K", hours=24)
    assert len(tl) >= 2
    assert all(t["band"] == "20m" for t in tl)


def test_prune(db):
    db.record(make(ts=time.time() - 10 * 86400))
    db.record(make(call="JA1NUT"))
    removed = db.prune(keep_days=7)
    assert removed == 1
    assert [r["dx_call"] for r in db.recent(86400)] == ["JA1NUT"]


def test_case_insensitive_call_queries(db):
    db.record(make())
    assert db.activity_summary("3y0k")
    assert db.timeline("3y0k")
