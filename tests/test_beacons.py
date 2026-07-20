from app.propagation.beacons import (BANDS_KHZ, BEACONS, CYCLE_S,
                                     current_slot, transmitting_now)


def test_cycle_length():
    assert CYCLE_S == 180
    assert len(BEACONS) == 18
    assert len(BANDS_KHZ) == 5


def test_slot_zero_is_4u1un_on_20m():
    now = transmitting_now(0)
    assert now[0]["freq"] == 14100.0
    assert now[0]["call"] == "4U1UN"


def test_beacon_steps_up_in_band():
    # 4U1UN: slot 0 on 14100, slot 1 on 18110, ...
    for band_i in range(5):
        entries = transmitting_now(band_i * 10)
        assert entries[band_i]["call"] == "4U1UN"


def test_second_slot_20m_is_ve8at():
    assert transmitting_now(10)[0]["call"] == "VE8AT"


def test_wraparound():
    a = transmitting_now(5)
    b = transmitting_now(5 + 180)
    assert [e["call"] for e in a] == [e["call"] for e in b]


def test_slot_index():
    assert current_slot(0) == 0
    assert current_slot(179.9) == 17
    assert current_slot(180) == 0


def test_one_beacon_per_band_all_slots():
    for slot in range(18):
        entries = transmitting_now(slot * 10)
        calls = [e["call"] for e in entries]
        assert len(set(calls)) == 5  # five different beacons across five bands
