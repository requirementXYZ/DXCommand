"""LoTW direct sync: pull worked and confirmed QSOs straight from ARRL's
Logbook of the World, no ADIF export needed.

Uses the documented user-query endpoint
  https://lotw.arrl.org/lotwuser/lotwreport.adi
authenticated with the operator's LoTW *website* username/password (the same
credentials every logging program uses for LoTW download). Two reports:
  qso_qsl=no  -> every QSO you uploaded            -> "worked"
  qso_qsl=yes -> every QSL (confirmation) received -> "confirmed"
Both come back as ADIF including DXCC/COUNTRY detail, which feeds the same
tracker as file imports. Sync is incremental: since-dates are remembered in
data/lotw_state.json (with a 2-day overlap for safety), per ARRL's guidance
to avoid re-downloading the full log each time.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOTW_URL = "https://lotw.arrl.org/lotwuser/lotwreport.adi"
TIMEOUT = 120  # a first full-log download can be slow


class LotwError(Exception):
    pass


def build_params(username: str, password: str, qsl: bool,
                 since: str | None) -> dict:
    params = {
        "login": username,
        "password": password,
        "qso_query": "1",
        "qso_qsl": "yes" if qsl else "no",
        "qso_qsldetail": "yes",     # include DXCC / COUNTRY fields
        "qso_mydetail": "no",
    }
    if since:
        params["qso_qslsince" if qsl else "qso_qsorxsince"] = since
    return params


def _sanitize(text: str, password: str) -> str:
    """Never let the password leak into logs/errors via a URL echo."""
    return text.replace(password, "***") if password else text


def validate_report(text: str) -> None:
    head = text[:2000]
    if re.search(r"password\s+(is\s+)?incorrect|invalid\s+(login|user)", head, re.I):
        raise LotwError("LoTW rejected the username/password")
    if "<eoh>" not in text.lower() and "arrl" not in head.lower():
        raise LotwError("unexpected response from LoTW (not an ADIF report)")


def fetch_report(username: str, password: str, qsl: bool,
                 since: str | None) -> str:
    import httpx
    try:
        r = httpx.get(LOTW_URL, params=build_params(username, password, qsl, since),
                      timeout=TIMEOUT, follow_redirects=True)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - network/HTTP errors of all kinds
        raise LotwError(_sanitize(f"LoTW request failed: {exc}", password)) from None
    validate_report(r.text)
    return r.text


class LotwSync:
    def __init__(self, state_path: Path, fetch=fetch_report) -> None:
        self.state_path = state_path
        self.fetch = fetch                  # injectable for tests
        try:
            self.state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.state = {}

    def _save_state(self) -> None:
        self.state_path.write_text(json.dumps(self.state), encoding="utf-8")

    def sync(self, username: str, password: str, tracker) -> dict:
        """Blocking (run in a thread). Returns per-report import stats."""
        if not username or not password:
            raise LotwError("LoTW username and password are not set (see SETUP)")
        results = {}
        for qsl, key in ((False, "qso_since"), (True, "qsl_since")):
            since = self.state.get(key)
            text = self.fetch(username, password, qsl, since)
            res = tracker.import_adif(text, force_confirmed=qsl)
            results["confirmed" if qsl else "worked"] = res
        # Overlap the next incremental window by 2 days to absorb processing lag.
        next_since = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
        self.state["qso_since"] = next_since
        self.state["qsl_since"] = next_since
        self.state["last_sync"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._save_state()
        return {
            "worked_qsos": results["worked"]["qsos"],
            "confirmed_qsls": results["confirmed"]["qsos"],
            "slots_added": (results["worked"]["slots_added"]
                            + results["confirmed"]["slots_added"]),
            "entities": results["confirmed"]["entities"],
            "last_sync": self.state["last_sync"],
        }
