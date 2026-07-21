"""Log auto-sync: watch ADIF files and re-import when they change.

Point it at your logger's ADIF export and/or WSJT-X's wsjtx_log.adi and the
needed-flags stay truthful without manual imports. LoTW/QSL fields in the
files mark slots confirmed.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

WSJTX_DEFAULT = Path(os.environ.get("LOCALAPPDATA", "")) / "WSJT-X" / "wsjtx_log.adi"


def resolve_paths(cfg_logsync: dict) -> list[Path]:
    paths = [Path(p) for p in cfg_logsync.get("paths", []) if str(p).strip()]
    if cfg_logsync.get("auto_wsjtx", True) and WSJTX_DEFAULT.exists():
        if WSJTX_DEFAULT not in paths:
            paths.append(WSJTX_DEFAULT)
    return paths


class LogSync:
    def __init__(self, get_cfg, tracker, on_imported) -> None:
        self._get_cfg = get_cfg          # callable -> logsync config dict
        self.tracker = tracker
        self.on_imported = on_imported   # callable(path_name, result_dict)
        self._mtimes: dict[Path, float] = {}
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="logsync")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    def check_once(self, initial: bool = False) -> list[tuple[str, dict]]:
        """Scan watched files; import any that changed. Returns import results."""
        results = []
        for path in resolve_paths(self._get_cfg()):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            known = self._mtimes.get(path)
            self._mtimes[path] = mtime
            if known == mtime:
                continue
            if initial and known is None:
                # First sighting at startup: import silently to seed state.
                pass
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            result = self.tracker.import_adif(text)
            results.append((path.name, result))
            self.on_imported(path.name, result)
        return results

    async def _run(self) -> None:
        # Initial import seeds worked-state from existing logs.
        await asyncio.to_thread(self.check_once, True)
        while True:
            try:
                poll = max(int(self._get_cfg().get("poll_s", 30)), 5)
                await asyncio.sleep(poll)
                await asyncio.to_thread(self.check_once)
            except asyncio.CancelledError:
                return
            except Exception as exc:  # noqa: BLE001 - keep the watcher alive
                print(f"[logsync] {exc}")
