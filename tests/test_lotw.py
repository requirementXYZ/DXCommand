from pathlib import Path

import pytest

from app.dxcc.cty import CtyDatabase
from app.dxcc.lotw import (LotwError, LotwSync, build_params, validate_report,
                           _sanitize)
from app.dxcc.tracker import NeededTracker

BUNDLED = Path(__file__).resolve().parent.parent / "app" / "bundled" / "cty_builtin.dat"

WORKED_ADIF = """ARRL Logbook of the World Status Report
<eoh>
<CALL:6>JA1NUT <BAND:3>20M <MODE:2>CW <COUNTRY:5>JAPAN <eor>
<CALL:5>G4IRN <BAND:3>40M <MODE:3>FT8 <COUNTRY:7>ENGLAND <eor>
"""
QSL_ADIF = """ARRL Logbook of the World Status Report
<eoh>
<CALL:6>JA1NUT <BAND:3>20M <MODE:2>CW <COUNTRY:5>JAPAN <eor>
"""


def test_build_params_incremental_keys():
    p = build_params("me", "pw", qsl=False, since="2026-07-01")
    assert p["qso_qsl"] == "no" and p["qso_qsorxsince"] == "2026-07-01"
    p2 = build_params("me", "pw", qsl=True, since="2026-07-01")
    assert p2["qso_qsl"] == "yes" and p2["qso_qslsince"] == "2026-07-01"
    assert "qso_qsorxsince" not in p2
    p3 = build_params("me", "pw", qsl=True, since=None)
    assert "qso_qslsince" not in p3


def test_validate_report():
    validate_report(WORKED_ADIF)                      # no raise
    with pytest.raises(LotwError, match="username/password"):
        validate_report("<html>Username/password incorrect</html>")
    with pytest.raises(LotwError, match="ADIF"):
        validate_report("<html>totally unrelated page</html>")
    # An error page that merely mentions ARRL must NOT pass (regression:
    # bogus credentials looked like a successful 0-QSO sync)
    with pytest.raises(LotwError, match="ADIF"):
        validate_report("<html>ARRL Logbook of the World - something went wrong</html>")


def test_password_never_leaks():
    assert "hunter2" not in _sanitize("error at url?password=hunter2", "hunter2")


@pytest.fixture()
def tracker(tmp_path):
    return NeededTracker(CtyDatabase.from_file(BUNDLED), tmp_path / "w.json")


def test_sync_imports_worked_and_confirmed(tmp_path, tracker):
    calls = []

    def fake_fetch(user, pw, qsl, since):
        calls.append((qsl, since))
        return QSL_ADIF if qsl else WORKED_ADIF

    sync = LotwSync(tmp_path / "state.json", fetch=fake_fetch)
    result = sync.sync("me", "pw", tracker)
    assert result["worked_qsos"] == 2
    assert result["confirmed_qsls"] == 1
    # Confirmed report upgrades JA 20m CW to "C"; England stays "W".
    # Entity names come from cty resolution (not LoTW's uppercase COUNTRY),
    # so LoTW and file imports land on the same rows.
    assert tracker.slot_status("Japan", "20m", "CW") == "C"
    assert tracker.slot_status("England", "40m", "FT8") == "W"
    assert "JAPAN" not in tracker.worked
    # First run has no since-dates
    assert calls == [(False, None), (True, None)]
    # Second run is incremental
    sync2 = LotwSync(tmp_path / "state.json", fetch=fake_fetch)
    sync2.sync("me", "pw", tracker)
    assert calls[2][1] is not None and calls[3][1] is not None


def test_sync_requires_credentials(tmp_path, tracker):
    sync = LotwSync(tmp_path / "state.json", fetch=lambda *a: WORKED_ADIF)
    with pytest.raises(LotwError, match="not set"):
        sync.sync("", "", tracker)


def test_fetch_error_wrapped(tmp_path, tracker):
    def boom(user, pw, qsl, since):
        raise LotwError("LoTW request failed: timeout")

    sync = LotwSync(tmp_path / "state.json", fetch=boom)
    with pytest.raises(LotwError):
        sync.sync("me", "pw", tracker)
    # failed sync must not advance the incremental window
    assert "qso_since" not in sync.state
