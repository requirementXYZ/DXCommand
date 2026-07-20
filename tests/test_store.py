import time

from app.spots.parser import Spot
from app.spots.store import SpotStore


def make(call="3Y0K", freq=14023.0, band="20m", ts=None, **kw) -> Spot:
    return Spot(dx_call=call, freq=freq, band=band,
                ts=ts if ts is not None else time.time(), **kw)


def test_new_and_refresh():
    st = SpotStore()
    s1, new1 = st.add(make(comment="UP 2"))
    assert new1
    s2, new2 = st.add(make(freq=14023.4, comment="UP 2.5", split_tx_khz=14025.5))
    assert not new2                       # within 1 kHz -> refresh
    assert s2 is s1
    assert s1.freq == 14023.4
    assert s1.split_tx_khz == 14025.5
    assert len(st.all()) == 1


def test_distinct_freq_is_new_spot():
    st = SpotStore()
    st.add(make(freq=14023.0))
    _, new = st.add(make(freq=14090.0))   # same call, FT8 freq elsewhere
    assert new
    assert len(st.all()) == 2


def test_age_out():
    st = SpotStore(max_age_s=10)
    st.add(make(ts=time.time() - 60))
    st.add(make(call="JA1NUT", freq=14012.0))
    assert [s.dx_call for s in st.all()] == ["JA1NUT"]


def test_cap():
    st = SpotStore(max_count=5)
    for i in range(8):
        st.add(make(call=f"K{i}AA", freq=14000.0 + i * 3, ts=time.time() + i))
    assert len(st.all()) == 5
    calls = {s.dx_call for s in st.all()}
    assert "K7AA" in calls and "K0AA" not in calls
