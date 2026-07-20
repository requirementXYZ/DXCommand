from pathlib import Path

import pytest

from app.dxcc.cty import CtyDatabase, bearing_distance

BUNDLED = Path(__file__).resolve().parent.parent / "app" / "bundled" / "cty_builtin.dat"


@pytest.fixture(scope="module")
def db() -> CtyDatabase:
    return CtyDatabase.from_file(BUNDLED)


def test_parses_entities(db):
    assert len(db.entities) > 80


@pytest.mark.parametrize("call,name", [
    ("K1ABC", "United States"),
    ("W6WX", "United States"),
    ("JA1NUT", "Japan"),
    ("7K4XYZ", "Japan"),
    ("3Y0K", "Bouvet"),
    ("VP8PIE", "Falkland Islands"),
    ("VK9XCX", "Christmas Island"),
    ("VK2GR", "Australia"),
    ("CE0YHF", "Easter Island"),
    ("CE3AA", "Chile"),
    ("E51DWC", "South Cook Islands"),
    ("GM3XYZ", "Scotland"),
    ("G4IRN", "England"),
    ("CT3MD", "Madeira Islands"),
    ("CT1ABC", "Portugal"),
    ("EA8ZZ", "Canary Islands"),
    ("EA5WU", "Spain"),
    ("UA9MA", "Asiatic Russia"),
    ("UA3AA", "European Russia"),
    ("RR9O", "Asiatic Russia"),
    ("4U1UN", "United Nations HQ"),
    ("P5DX", "North Korea"),
    ("HB0A", "Liechtenstein"),
    ("HB9CVQ", "Switzerland"),
    ("A25RU", "Botswana"),
    ("A45XR", "Oman"),
])
def test_lookup(db, call, name):
    ent = db.lookup(call)
    assert ent is not None, f"{call} unresolved"
    assert ent.name == name


def test_portable_call(db):
    assert db.lookup("F/G3XYZ").name == "France"
    assert db.lookup("K5D/P").name == "United States"


def test_unknown(db):
    assert db.lookup("QQQQQ") is None


def test_longitude_sign(db):
    ja = db.lookup("JA1NUT")
    assert ja.lon > 100  # Japan is east-positive after conversion
    k = db.lookup("K1ABC")
    assert k.lon < -60


def test_load_database_offline_uses_bundled_and_records_source(tmp_path):
    from app.config import BUNDLED_DIR
    from app.dxcc.cty import load_database
    db = load_database(tmp_path, BUNDLED_DIR, offline=True)
    assert db.source == "cty_builtin.dat"
    assert len(db.entities) > 80


def test_bearing_distance():
    az, dist = bearing_distance(41.7, -72.7, 36.4, 138.4)  # CT USA -> Japan
    assert 320 <= az <= 350
    assert 10000 <= dist <= 11500
