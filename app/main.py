"""DX Command server: wires rig, spots, DXCC, propagation, WSJT-X and the web UI.

All sources (rig / spot feeds / FT8 decodes / solar) are hot-swappable at runtime
via POST /api/config, so the browser Setup panel can switch between demo
simulators and the real OmniRig / cluster / RBN / WSJT-X without a restart.
"""
from __future__ import annotations

import asyncio
import contextlib
import re
import time

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .alerts import AlertEngine
from .bus import EventBus
from .config import (BUNDLED_DIR, DATA_DIR, STATIC_DIR, _merge, grid_to_latlon,
                     load_config, save_config, update_config_file)
from .dxcc.cty import bearing_distance, load_database
from .dxcc.logsync import LogSync
from .dxcc.tracker import NeededTracker
from .dxped.calendar import load_dxpeditions
from .propagation.beacons import transmitting_now
from .propagation.solar import SolarService
from .rig.base import mode_for_spot
from .rig.simulator import SimulatedRig
from .spots.cluster_client import ClusterClient
from .spots.parser import BANDS, Spot, band_for
from .spots.persist import SpotDB
from .spots.simulator import SpotSimulator
from .spots.store import SpotStore
from .wsjtx.listener import WsjtxService
from .wsjtx.protocol import Decode, QsoLogged, Status
from .wsjtx.simulator import WsjtxSimulator

WORLDMAP_URL = ("https://raw.githubusercontent.com/johan/world.geo.json/"
                "master/countries.geo.json")
MATRIX_BANDS = [name for name, _, _ in BANDS if name != "60m"]
MATRIX_MODES = ["CW", "FT8", "FT4", "SSB"]

cfg = load_config()
bus = EventBus()
app = FastAPI(title="DX Command", version=__version__)

HOME_LAT, HOME_LON = grid_to_latlon(cfg.grid)
cty = load_database(DATA_DIR, BUNDLED_DIR, cfg.offline)
tracker = NeededTracker(cty, DATA_DIR / "worked.json")
store = SpotStore(max_age_s=cfg["spots"]["max_age_min"] * 60,
                  max_count=cfg["spots"]["max_count"])
spotdb = SpotDB(DATA_DIR / "spots.db")
watch_list: set[str] = {c.upper() for c in cfg["watch_list"]}

_loop: asyncio.AbstractEventLoop | None = None

# Active services (hot-swappable)
rig = None
spot_source = None            # ClusterClient | SpotSimulator
rbn_client: ClusterClient | None = None
solar_svc: SolarService | None = None
wsjtx_svc = None              # WsjtxService | WsjtxSimulator | None
logsync_svc: LogSync | None = None
_config_lock = asyncio.Lock()


def my_continent() -> str:
    ent = cty.lookup(cfg.callsign)
    return ent.cont if ent else "NA"


alert_engine = AlertEngine(lambda: cfg["alerts"], my_continent(),
                           lambda frame: bus.publish("alert", frame, sticky=False))


# ---------------------------------------------------------------- enrichment
def enrich(spot: Spot) -> Spot:
    ent = cty.lookup(spot.dx_call)
    if ent:
        az, dist = bearing_distance(HOME_LAT, HOME_LON, ent.lat, ent.lon)
        spot.dxcc = {**ent.to_dict(), "azimuth": az, "distance_km": dist}
    spot.needed = tracker.needed(spot.dx_call, spot.band, spot.mode)
    spot.watched = spot.dx_call in watch_list
    for sp in spot.spotters:
        if not sp.get("cont"):
            s_ent = cty.lookup(sp["call"])
            sp["cont"] = s_ent.cont if s_ent else None
    return spot


def on_spot(spot: Spot) -> None:
    spot.watched = spot.dx_call in watch_list
    keep = cfg["cluster"].get("keep_modes")
    if keep and spot.mode not in keep and not spot.watched:
        return
    enrich(spot)
    spotdb.record(spot)
    stored, _is_new = store.add(spot)
    alert_engine.check_spot(stored)
    bus.publish("spot", stored.to_dict(), sticky=False)


def on_cluster_status(msg: str) -> None:
    bus.publish("cluster_status", {"text": msg, "ts": int(time.time())})


def on_rbn_status(msg: str) -> None:
    bus.publish("rbn_status", {"text": msg, "ts": int(time.time())})


def on_rig_change(state) -> None:
    # May be called from the OmniRig COM thread.
    if _loop and _loop.is_running():
        _loop.call_soon_threadsafe(bus.publish, "rig", state.to_dict())


CALL_RE = re.compile(r"^[A-Z0-9/]{3,}$")


def sender_of(message: str) -> str | None:
    """Extract the transmitting callsign from an FT8 message."""
    toks = message.replace("<", "").replace(">", "").split()
    if not toks:
        return None
    if toks[0] == "CQ":
        for t in toks[1:]:
            if len(t) >= 3 and any(c.isdigit() for c in t) and CALL_RE.match(t):
                return t
        return None
    if len(toks) >= 2 and CALL_RE.match(toks[1]) and any(c.isdigit() for c in toks[1]):
        return toks[1]
    return None


def on_wsjtx_decode(d: Decode) -> None:
    call = sender_of(d.message)
    ent = cty.lookup(call) if call else None
    frame = {
        "key": f"{d.time_ms}|{d.delta_f}|{d.message}",
        "time_ms": d.time_ms, "snr": d.snr, "dt": d.delta_t, "df": d.delta_f,
        "message": d.message, "call": call,
        "cq": d.message.startswith("CQ "),
        "entity": ent.name if ent else None,
        "cont": ent.cont if ent else None,
        "needed": tracker.needed(call, "", "FT8") if call else "",
        "watched": bool(call and call in watch_list),
    }
    alert_engine.check_decode(frame)
    bus.publish("wsjtx_decode", frame, sticky=False)


def on_wsjtx_status(s: Status) -> None:
    bus.publish("wsjtx_status", {
        "dial_mhz": s.dial_freq / 1e6, "mode": s.mode, "dx_call": s.dx_call,
        "transmitting": s.transmitting, "de_call": s.de_call, "ts": int(time.time()),
    })


def on_wsjtx_qso(q: QsoLogged) -> None:
    band = band_for(q.tx_freq / 1000)
    mode = "FT8" if q.mode.upper() in ("FT8", "MFSK") else q.mode.upper()
    tracker.record_qso(q.dx_call, band, mode)
    bus.publish("qso_logged", {"call": q.dx_call, "band": band, "mode": mode},
                sticky=False)
    bus.publish("tracker_stats", tracker.stats())


def on_log_imported(name: str, result: dict) -> None:
    for s in store.all():
        s.needed = tracker.needed(s.dx_call, s.band, s.mode)
    bus.publish("tracker_stats", tracker.stats())
    bus.publish("log_sync", {"file": name, **result, "ts": int(time.time())},
                sticky=False)


# ------------------------------------------------------- service management
async def refresh_cty() -> None:
    """If we're online but still running on the bundled prefix subset,
    download the full cty.dat now and swap it in — no restart needed."""
    global cty
    if cfg.offline or cty.source == "cty.dat":
        return
    new_db = await asyncio.to_thread(load_database, DATA_DIR, BUNDLED_DIR, False)
    if new_db.source == "cty.dat":
        cty = new_db
        tracker.cty = new_db


async def start_rig() -> None:
    global rig
    if rig:
        with contextlib.suppress(Exception):
            await rig.stop()
    if cfg["rig"]["backend"] == "omnirig":
        from .rig.omnirig_backend import OmniRigBackend
        rig = OmniRigBackend(cfg["rig"]["rig_number"], cfg["rig"]["poll_ms"],
                             on_change=on_rig_change)
    else:
        rig = SimulatedRig(on_change=lambda st: bus.publish("rig", st.to_dict()))
    await rig.start()
    bus.publish("rig", rig.get_state().to_dict())


async def start_spot_source() -> None:
    global spot_source, rbn_client
    for svc in (spot_source, rbn_client):
        if svc:
            with contextlib.suppress(Exception):
                await svc.stop()
    rbn_client = None
    if cfg["cluster"].get("simulate"):
        spot_source = SpotSimulator(on_spot, on_cluster_status)
        bus.publish("rbn_status", {"text": "simulated (RBN spots mixed in)",
                                   "ts": int(time.time())})
    else:
        spot_source = ClusterClient(cfg["cluster"]["host"], cfg["cluster"]["port"],
                                    cfg.callsign, on_spot, on_cluster_status,
                                    cfg["cluster"].get("init_commands"))
        if cfg["rbn"].get("enabled", True):
            rbn_client = ClusterClient(cfg["rbn"]["host"], cfg["rbn"]["port"],
                                       cfg.callsign, on_spot, on_rbn_status,
                                       init_commands=[])
            rbn_client.start()
        else:
            bus.publish("rbn_status", {"text": "disabled", "ts": int(time.time())})
    spot_source.start()


async def start_wsjtx() -> None:
    global wsjtx_svc
    if wsjtx_svc:
        with contextlib.suppress(Exception):
            await wsjtx_svc.stop()
        wsjtx_svc = None
    if cfg["wsjtx"].get("simulate"):
        wsjtx_svc = WsjtxSimulator(on_wsjtx_decode, on_wsjtx_status, cfg.callsign)
        wsjtx_svc.start()
    elif cfg["wsjtx"]["enabled"]:
        wsjtx_svc = WsjtxService(cfg["wsjtx"]["udp_port"], on_wsjtx_decode,
                                 on_wsjtx_status, on_wsjtx_qso,
                                 lambda cid: bus.publish(
                                     "wsjtx_status",
                                     {"heartbeat": cid, "ts": int(time.time())}))
        await wsjtx_svc.start()
        bus.publish("wsjtx_status", {"listening": cfg["wsjtx"]["udp_port"],
                                     "ts": int(time.time())})
    else:
        bus.publish("wsjtx_status", {"disabled": True, "ts": int(time.time())})


async def start_solar() -> None:
    global solar_svc
    if solar_svc:
        with contextlib.suppress(Exception):
            await solar_svc.stop()
    solar_svc = SolarService(cfg.offline, lambda d: bus.publish("solar", d))
    solar_svc.start()


def publish_app_info() -> None:
    bus.publish("app_info", {
        "version": __version__, "callsign": cfg.callsign, "grid": cfg.grid,
        "demo": cfg["rig"]["backend"] == "simulator",
        "home": {"lat": HOME_LAT, "lon": HOME_LON},
        "my_continent": my_continent(),
        "watch_list": sorted(watch_list),
        "alerts": cfg["alerts"],
    })


def seed_store_from_history() -> None:
    """Rebuild the in-memory spot list from persisted events after a restart."""
    events = spotdb.recent(cfg["spots"]["max_age_min"] * 60)
    for ev in events:
        spot = Spot(dx_call=ev["dx_call"], freq=ev["freq"], band=ev["band"],
                    mode=ev["mode"], ts=ev["ts"], spotter=ev["spotter"] or "",
                    comment=ev["comment"] or "", source=ev["source"] or "history",
                    snr=ev["snr"], split_tx_khz=ev["split_tx"])
        spot.spotters = [{"call": spot.spotter, "cont": None, "snr": spot.snr,
                          "ts": spot.ts}]
        enrich(spot)
        store.add(spot)
    if events:
        print(f"[persist] restored {len(store.all())} spots from history")


# ---------------------------------------------------------------- lifecycle
@app.on_event("startup")
async def startup() -> None:
    global _loop, logsync_svc
    _loop = asyncio.get_running_loop()
    seed_store_from_history()
    await start_rig()
    await start_spot_source()
    await start_solar()
    await start_wsjtx()
    logsync_svc = LogSync(lambda: cfg["logsync"], tracker, on_log_imported)
    logsync_svc.start()
    asyncio.create_task(beacon_ticker(), name="beacons")
    asyncio.create_task(publish_dxped(), name="dxped")
    bus.publish("tracker_stats", tracker.stats())
    publish_app_info()


@app.on_event("shutdown")
async def shutdown() -> None:
    for s in (spot_source, rbn_client, solar_svc, wsjtx_svc, logsync_svc, rig):
        if s:
            with contextlib.suppress(Exception):
                await s.stop()
    spotdb.close()


async def beacon_ticker() -> None:
    while True:
        bus.publish("beacons", transmitting_now(time.time()))
        await asyncio.sleep(2)


async def publish_dxped() -> None:
    data = await load_dxpeditions(DATA_DIR, BUNDLED_DIR, cfg.offline)
    bus.publish("dxped", data)


# ---------------------------------------------------------------- websocket
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    q = bus.subscribe()
    try:
        for frame in bus.snapshot():
            await ws.send_text(frame)
        while True:
            await ws.send_text(await q.get())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        bus.unsubscribe(q)


# ---------------------------------------------------------------- REST API
@app.get("/api/spots")
async def api_spots():
    return [s.to_dict() for s in store.all()]


@app.get("/api/alerts")
async def api_alerts():
    return list(alert_engine.log)


@app.get("/api/worked")
async def api_worked():
    """Full worked/confirmed state for the DXCC table view."""
    return {"bands": MATRIX_BANDS, "modes": MATRIX_MODES,
            "entities": tracker.worked, "stats": tracker.stats()}


@app.get("/api/matrix")
async def api_matrix(call: str):
    call = call.upper().strip()
    ent = cty.lookup(call)
    if not ent:
        return JSONResponse({"error": f"cannot resolve {call} to a DXCC entity"},
                            status_code=404)
    return {
        "call": call,
        "entity": ent.to_dict(),
        "bands": MATRIX_BANDS,
        "modes": MATRIX_MODES,
        "status": tracker.entity_matrix(ent.name, MATRIX_BANDS, MATRIX_MODES),
        "activity": spotdb.activity_summary(call),
        "timeline": spotdb.timeline(call, 24),
        "watched": call in watch_list,
    }


@app.post("/api/rig/tune")
async def api_tune(req: Request):
    body = await req.json()
    freq_hz = int(float(body["freq_khz"]) * 1000)
    mode = mode_for_spot(body["mode"]) if body.get("mode") else None
    split_tx = (int(float(body["split_tx_khz"]) * 1000)
                if body.get("split_tx_khz") else None)
    await rig.tune(freq_hz, mode, split_tx)
    return {"ok": True, "freq_hz": freq_hz, "mode": mode, "split_tx_hz": split_tx}


@app.post("/api/rig/freq")
async def api_freq(req: Request):
    body = await req.json()
    await rig.set_simplex(int(body["freq_hz"]))
    return {"ok": True}


@app.post("/api/rig/mode")
async def api_mode(req: Request):
    body = await req.json()
    await rig.set_mode(body["mode"])
    return {"ok": True}


@app.get("/api/rig")
async def api_rig():
    return rig.get_state().to_dict()


@app.get("/api/config")
async def api_config_get():
    return cfg.raw


@app.post("/api/config")
async def api_config_set(req: Request):
    """Apply settings from the Setup panel: persist and hot-swap services."""
    global HOME_LAT, HOME_LON
    body = await req.json()
    allowed = {"callsign", "grid", "rig", "cluster", "wsjtx", "rbn",
               "alerts", "logsync", "offline"}
    patch = {k: v for k, v in body.items() if k in allowed}
    if "callsign" in patch:
        patch["callsign"] = str(patch["callsign"]).upper().strip() or "N0CALL"
    if "grid" in patch and not re.fullmatch(
            r"[A-Ra-r]{2}\d{2}([A-Xa-x]{2})?", str(patch["grid"]).strip()):
        return JSONResponse({"ok": False, "error": "grid must look like IO95 or IO95rj"},
                            status_code=400)
    # Only service-affecting keys warrant restarting connections; alert or
    # log-sync tweaks must not drop the cluster/rig/WSJT-X links.
    service_keys = {"callsign", "grid", "rig", "cluster", "wsjtx", "rbn", "offline"}
    services_touched = bool(service_keys & patch.keys())
    async with _config_lock:
        cfg.raw = _merge(cfg.raw, patch)
        save_config(cfg.raw)
        if services_touched:
            # Explicit UI choices override any launch-time demo forcing.
            cfg.raw["demo_mode"] = False
            save_config(cfg.raw)
            HOME_LAT, HOME_LON = grid_to_latlon(cfg.grid)
            await refresh_cty()      # pull the full country list if now online
            alert_engine.my_continent = my_continent()
            await start_rig()
            await start_spot_source()
            await start_solar()
            await start_wsjtx()
            asyncio.create_task(publish_dxped(), name="dxped-refresh")
            for s in store.all():
                enrich(s)
        publish_app_info()
    return {"ok": True, "config": cfg.raw,
            "cty": {"entities": len(cty.entities), "source": cty.source}}


@app.post("/api/adif")
async def api_adif(req: Request):
    text = (await req.body()).decode("utf-8", "replace")
    result = tracker.import_adif(text)
    on_log_imported("manual import", result)
    return result


@app.post("/api/watch")
async def api_watch(req: Request):
    body = await req.json()
    call = body["call"].upper().strip()
    if body.get("remove"):
        watch_list.discard(call)
    else:
        watch_list.add(call)
    for s in store.all():
        s.watched = s.dx_call in watch_list
    cfg.raw["watch_list"] = sorted(watch_list)
    update_config_file(watch_list=sorted(watch_list))
    bus.publish("watch_list", sorted(watch_list))
    return {"watch_list": sorted(watch_list)}


@app.post("/api/wsjtx/reply")
async def api_wsjtx_reply(req: Request):
    body = await req.json()
    ok = (isinstance(wsjtx_svc, WsjtxService) and wsjtx_svc.reply_to(body["key"]))
    return {"ok": ok, "reason": None if ok else "WSJT-X not connected (or demo mode)"}


@app.get("/api/worldmap")
async def api_worldmap():
    cache = DATA_DIR / "worldmap.geo.json"
    if not cache.exists() and not cfg.offline:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                r = await client.get(WORLDMAP_URL)
                r.raise_for_status()
            cache.write_bytes(r.content)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": str(exc)}, status_code=404)
    if cache.exists():
        return FileResponse(cache, media_type="application/geo+json")
    return JSONResponse({"error": "offline"}, status_code=404)


@app.middleware("http")
async def no_stale_assets(request: Request, call_next):
    """Force revalidation of JS/CSS/HTML so upgrades never run mixed cached
    frontend files against a newer backend (localhost app: cost is nil)."""
    response = await call_next(request)
    if not request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache"
    return response


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
