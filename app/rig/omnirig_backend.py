"""OmniRig COM backend.

OmniRig (VE3NEA) exposes a COM automation server `OmniRig.OmniRigX` with Rig1/Rig2
objects. COM objects must be used from the thread that created them, so this
backend runs a dedicated STA thread that owns the COM object, polls rig state,
and executes commands from a queue. The asyncio side only ever touches the
thread-safe queue and the last-published immutable state.
"""
from __future__ import annotations

import queue
import threading
import time

from .base import RigBackend, RigState

# RigParamX constants from OmniRig's type library (RigX.pas).
PM_UNKNOWN = 0x00000001
PM_SPLITON = 0x00008000
PM_SPLITOFF = 0x00010000
PM_RX = 0x00200000
PM_TX = 0x00400000
PM_CW_U = 0x00800000
PM_CW_L = 0x01000000
PM_SSB_U = 0x02000000
PM_SSB_L = 0x04000000
PM_DIG_U = 0x08000000
PM_DIG_L = 0x10000000
PM_AM = 0x20000000
PM_FM = 0x40000000

MODE_TO_PM = {
    "CW": PM_CW_U,
    "CW-R": PM_CW_L,
    "USB": PM_SSB_U,
    "LSB": PM_SSB_L,
    "DATA-U": PM_DIG_U,
    "DATA-L": PM_DIG_L,
    "AM": PM_AM,
    "FM": PM_FM,
}
PM_TO_MODE = {v: k for k, v in MODE_TO_PM.items()}

ST_ONLINE = 4  # RigStatusX.ST_ONLINE


class OmniRigBackend(RigBackend):
    def __init__(self, rig_number: int = 1, poll_ms: int = 300, on_change=None) -> None:
        self._rig_number = 1 if rig_number != 2 else 2
        self._poll_s = max(poll_ms, 100) / 1000
        self._on_change = on_change          # callable(RigState), called from COM thread
        self._cmd: queue.Queue = queue.Queue()
        self._state = RigState(status="Starting OmniRig...", backend="omnirig",
                               label=f"OmniRig Rig {self._rig_number}")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None

    # -- asyncio-facing API -------------------------------------------------
    async def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="omnirig", daemon=True)
        self._thread.start()

    async def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def get_state(self) -> RigState:
        return self._state

    async def set_freq(self, hz: int) -> None:
        self._cmd.put(("freq", int(hz)))

    async def set_mode(self, mode: str) -> None:
        self._cmd.put(("mode", mode))

    async def set_split(self, rx_hz: int, tx_hz: int) -> None:
        self._cmd.put(("split", (int(rx_hz), int(tx_hz))))

    async def set_simplex(self, hz: int) -> None:
        self._cmd.put(("simplex", int(hz)))

    # -- COM thread ---------------------------------------------------------
    def _run(self) -> None:
        try:
            import pythoncom
            import win32com.client
        except ImportError:
            self._fail("pywin32 not installed - run: pip install pywin32")
            return
        pythoncom.CoInitialize()
        try:
            try:
                omnirig = win32com.client.Dispatch("OmniRig.OmniRigX")
            except Exception as exc:  # noqa: BLE001 - COM raises pywintypes.com_error
                self._fail(f"OmniRig not available ({exc}). Install from dxatlas.com/omnirig")
                return
            rig = omnirig.Rig1 if self._rig_number == 1 else omnirig.Rig2
            while not self._stop.is_set():
                self._drain_commands(rig)
                self._poll(rig)
                time.sleep(self._poll_s)
        finally:
            pythoncom.CoUninitialize()

    def _fail(self, msg: str) -> None:
        self.last_error = msg
        self._publish(RigState(status=msg, online=False, backend="omnirig",
                               label=self._state.label))

    def _drain_commands(self, rig) -> None:
        while True:
            try:
                op, arg = self._cmd.get_nowait()
            except queue.Empty:
                return
            try:
                if op == "freq":
                    rig.Freq = arg
                elif op == "simplex":
                    rig.SetSimplexMode(arg)
                elif op == "split":
                    rig.SetSplitMode(arg[0], arg[1])
                elif op == "mode":
                    pm = MODE_TO_PM.get(arg)
                    if pm:
                        rig.Mode = pm
            except Exception as exc:  # noqa: BLE001
                self.last_error = f"{op} failed: {exc}"

    def _poll(self, rig) -> None:
        try:
            status_num = int(rig.Status)
            st = RigState(
                status=str(rig.StatusStr),
                online=(status_num == ST_ONLINE),
                backend="omnirig",
                label=f"OmniRig Rig {self._rig_number}: {rig.RigType}"
                if status_num == ST_ONLINE else self._state.label,
            )
            if st.online:
                st.freq = int(rig.GetRxFrequency() or rig.Freq or 0)
                st.tx_freq = int(rig.GetTxFrequency() or st.freq)
                st.freq_b = int(rig.FreqB or 0)
                st.mode = PM_TO_MODE.get(int(rig.Mode), "?")
                st.split = int(rig.Split) == PM_SPLITON
                st.tx = int(rig.Tx) == PM_TX
                st.rit = int(rig.RitOffset or 0)
        except Exception as exc:  # noqa: BLE001
            st = RigState(status=f"OmniRig error: {exc}", online=False,
                          backend="omnirig", label=self._state.label)
        self._publish(st)

    def _publish(self, st: RigState) -> None:
        changed = st.to_dict() != self._state.to_dict()
        self._state = st
        if changed and self._on_change:
            self._on_change(st)
