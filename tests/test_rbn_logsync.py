import time

from app.dxcc.logsync import LogSync, resolve_paths
from app.spots.parser import parse_spot_line
from app.spots.store import SpotStore


# ---------------- RBN skimmer spot parsing ----------------
def test_rbn_line_parses_with_snr():
    s = parse_spot_line(
        "DX de W3LPL-#:   14023.1  3Y0K           CW    24 dB  22 WPM  CQ      1834Z")
    assert s is not None
    assert s.spotter == "W3LPL"
    assert s.mode == "CW"
    assert s.snr == 24
    assert s.spotters[0]["call"] == "W3LPL"
    assert s.spotters[0]["snr"] == 24


def test_spotter_aggregation_across_sources():
    st = SpotStore()
    a = parse_spot_line("DX de W3LPL-#:  14023.0  3Y0K  CW 24 dB 22 WPM CQ  1834Z")
    b = parse_spot_line("DX de G4IRN:    14023.2  3Y0K  UP 2 loud           1835Z")
    c = parse_spot_line("DX de W3LPL-#:  14023.1  3Y0K  CW 30 dB 22 WPM CQ  1836Z")
    st.add(a)
    stored, is_new = st.add(b)
    assert not is_new
    st.add(c)
    calls = {sp["call"] for sp in stored.spotters}
    assert calls == {"W3LPL", "G4IRN"}
    w3 = next(sp for sp in stored.spotters if sp["call"] == "W3LPL")
    assert w3["snr"] == 30                  # refreshed by the newer skimmer spot
    assert stored.snr == 30                 # best SNR kept on the spot
    assert stored.split_tx_khz == 14025.2   # split hint retained from G4IRN


# ---------------- log auto-sync ----------------
class FakeTracker:
    def __init__(self):
        self.imported = []

    def import_adif(self, text):
        self.imported.append(text)
        return {"qsos": text.count("<eor>"), "slots_added": 0,
                "unresolved": 0, "entities": 0}


def test_resolve_paths_skips_blank_and_dedupes(tmp_path):
    p = tmp_path / "log.adi"
    p.write_text("x")
    cfg = {"paths": [str(p), ""], "auto_wsjtx": False}
    assert resolve_paths(cfg) == [p]


def test_check_once_imports_on_change(tmp_path):
    log = tmp_path / "log.adi"
    log.write_text("<eoh><call:5>G4IRN <band:3>20m <mode:2>CW <eor>")
    events = []
    tracker = FakeTracker()
    sync = LogSync(lambda: {"paths": [str(log)], "auto_wsjtx": False},
                   tracker, lambda name, res: events.append(name))
    r1 = sync.check_once(initial=True)
    assert len(r1) == 1 and events == ["log.adi"]
    # unchanged file -> no re-import
    assert sync.check_once() == []
    # touch with new content -> re-import
    time.sleep(0.01)
    log.write_text("<eoh><call:5>G4IRN <band:3>40m <mode:2>CW <eor>")
    import os
    os.utime(log, (time.time() + 5, time.time() + 5))
    assert len(sync.check_once()) == 1
    assert len(tracker.imported) == 2


def test_missing_file_is_skipped(tmp_path):
    sync = LogSync(lambda: {"paths": [str(tmp_path / "nope.adi")],
                            "auto_wsjtx": False},
                   FakeTracker(), lambda *a: None)
    assert sync.check_once() == []
