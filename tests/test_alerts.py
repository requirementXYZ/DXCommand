import time
from datetime import datetime

from app.alerts import AlertEngine
from app.spots.parser import Spot


def make_engine(cfg_overrides=None, my_cont="NA"):
    cfg = {"enabled": True, "notify_atno": True, "notify_band": False,
           "notify_mode": False, "notify_watch": True,
           "only_my_continent": False, "quiet": "", "sound": "ping"}
    cfg.update(cfg_overrides or {})
    emitted = []
    eng = AlertEngine(lambda: cfg, my_cont, emitted.append)
    return eng, emitted, cfg


def make_spot(call="3Y0K", band="20m", needed="atno", watched=False,
              spotter_conts=("EU",)):
    s = Spot(dx_call=call, freq=14023.0, band=band, mode="CW",
             needed=needed, watched=watched)
    s.spotters = [{"call": f"TEST{i}", "cont": c, "snr": 10, "ts": time.time()}
                  for i, c in enumerate(spotter_conts)]
    return s


def test_atno_alert_fires():
    eng, out, _ = make_engine()
    eng.check_spot(make_spot())
    assert len(out) == 1
    assert out[0]["reason"] == "atno"
    assert "ALL-TIME NEW ONE" in out[0]["text"]


def test_dedupe_within_window():
    eng, out, _ = make_engine()
    eng.check_spot(make_spot())
    eng.check_spot(make_spot())
    assert len(out) == 1
    eng.check_spot(make_spot(band="17m"))   # different band -> new alert
    assert len(out) == 2


def test_watch_beats_needed_and_ignores_continent_filter():
    eng, out, _ = make_engine({"only_my_continent": True})
    eng.check_spot(make_spot(needed="", watched=True, spotter_conts=("EU",)))
    assert out and out[0]["reason"] == "watch"


def test_band_mode_levels_respect_config():
    eng, out, _ = make_engine()
    eng.check_spot(make_spot(needed="band"))
    assert not out                          # notify_band defaults off
    eng2, out2, _ = make_engine({"notify_band": True, "notify_mode": True})
    eng2.check_spot(make_spot(needed="band"))
    eng2.check_spot(make_spot(call="VP8PIE", needed="mode"))
    assert [a["reason"] for a in out2] == ["band", "mode"]


def test_only_my_continent_filters_spots():
    eng, out, _ = make_engine({"only_my_continent": True}, my_cont="NA")
    eng.check_spot(make_spot(spotter_conts=("EU", "AS")))
    assert not out
    eng.check_spot(make_spot(call="VP8PIE", spotter_conts=("EU", "NA")))
    assert len(out) == 1


def test_disabled_engine_is_silent():
    eng, out, _ = make_engine({"enabled": False})
    eng.check_spot(make_spot())
    assert not out


def test_quiet_hours_same_day_and_overnight():
    eng, _, _ = make_engine({"quiet": "22:00-07:00"})
    assert eng.in_quiet_hours(datetime(2026, 7, 21, 23, 30))
    assert eng.in_quiet_hours(datetime(2026, 7, 21, 6, 59))
    assert not eng.in_quiet_hours(datetime(2026, 7, 21, 12, 0))
    eng2, _, _ = make_engine({"quiet": "09:00-17:00"})
    assert eng2.in_quiet_hours(datetime(2026, 7, 21, 12, 0))
    assert not eng2.in_quiet_hours(datetime(2026, 7, 21, 20, 0))
    eng3, _, _ = make_engine({"quiet": ""})
    assert not eng3.in_quiet_hours()
    eng4, _, _ = make_engine({"quiet": "garbage"})
    assert not eng4.in_quiet_hours()


def test_decode_alert_and_log():
    eng, out, _ = make_engine()
    eng.check_decode({"call": "3Y0K", "needed": "atno", "watched": False,
                      "entity": "Bouvet"})
    assert out and out[0]["kind"] == "ft8"
    assert list(eng.log)[0] is out[0]
    eng.check_decode({"call": "3Y0K", "needed": "atno", "watched": False})
    assert len(out) == 1                    # deduped
