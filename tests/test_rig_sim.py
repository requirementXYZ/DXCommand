import asyncio

import pytest

from app.rig.base import mode_for_spot
from app.rig.simulator import SimulatedRig


@pytest.fixture()
def rig() -> SimulatedRig:
    return SimulatedRig(latency_s=0.01)


def run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def test_simplex_tune(rig):
    async def go():
        await rig.start()
        await rig.tune(14_023_000, "CW")
        return rig.get_state()
    st = run(go())
    assert st.freq == 14_023_000
    assert st.tx_freq == 14_023_000
    assert st.mode == "CW"
    assert st.split is False


def test_split_tune(rig):
    async def go():
        await rig.tune(14_023_000, "CW", split_tx_hz=14_025_000)
        return rig.get_state()
    st = run(go())
    assert st.split is True
    assert st.freq == 14_023_000
    assert st.tx_freq == 14_025_000


def test_split_then_simplex_clears(rig):
    async def go():
        await rig.tune(14_023_000, "CW", split_tx_hz=14_025_000)
        await rig.tune(14_074_000, "FT8")
        return rig.get_state()
    st = run(go())
    assert st.split is False
    assert st.mode == "DATA-U"
    assert st.tx_freq == 14_074_000


def test_mode_mapping():
    assert mode_for_spot("FT8") == "DATA-U"
    assert mode_for_spot("FT4") == "DATA-U"
    assert mode_for_spot("CW") == "CW"


def test_tune_maps_spot_modes(rig):
    async def go():
        await rig.tune(28_074_000, "FT8")
        return rig.get_state()
    assert run(go()).mode == "DATA-U"
