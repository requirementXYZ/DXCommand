# DX Command — Specification

A modern, web-based DX dashboard for **CW (Morse)** and **FT8/FT4** operators chasing DXpeditions.
It re-imagines the functionality of the classic VE3NEA / DX Atlas (Afreet Software) tool
family in a single browser interface, controlling any radio supported by **OmniRig**.

Version: 1.0 &nbsp;•&nbsp; Date: 2026-07-21 &nbsp;•&nbsp; Platform: Windows 10/11, Python 3.11+

---

## 1. Heritage analysis — what we modernize, and what we ignore

Source material: https://dxatlas.com/ and https://github.com/VE3NEA

| Classic tool | What it does | Disposition in DX Command |
|---|---|---|
| **Band Master** | Downloads DX spots, graphical band map, OmniRig click-to-tune, country/azimuth lookup | **Core of the product.** Modern band map + spot table with CW/FT8 filtering, click-to-QSY, DXCC resolution, azimuth/distance |
| **OmniRig** (repo: `VE3NEA/OmniRig`) | COM rig-control engine supporting most transceivers | **Required integration point.** Backend talks to `OmniRig.OmniRigX` via COM; Rig 1/Rig 2, freq, mode, split |
| **CW Skimmer / CW Skimmer Server** | Wideband CW decoder producing spots | Not reimplemented (DSP out of scope). Its *output* is consumed: the Reverse Beacon Network and cluster nodes carry skimmer spots, which the dashboard ingests and labels |
| **JTSkimmer** (repo) / **WsjtxUtils** (repo) | FT8/FT4 decoding; WSJT-X UDP protocol library | **WSJT-X UDP listener** built in: live decode stream, CQ/DX highlighting, dial-frequency tracking, double-click-to-reply |
| **PskrDxClusterService** (repo) | Re-serves PSK Reporter MQTT FT8 spots as a telnet cluster | Dashboard's cluster client can point at any telnet cluster **including this service** for FT8-dense spot flow |
| **Morse Runner** (repo) | CW pileup simulator for training | **CW Pileup Trainer** module: Web-Audio pileup simulation with scoring — practice for the moment the DXpedition comes back to you |
| **HamCAP / DVOACAP / IonoProbe** | HF propagation prediction, ionospheric data | **Propagation panel**: live solar indices (SFI/SSN/A/K/X-ray) + per-band day/night condition summary. Full VOACAP modeling out of scope v1 |
| **DX Atlas** | World atlas, gray line, prefixes, azimuths | **Gray-line world map**: live solar terminator, spots plotted geographically, great-circle path + short/long-path azimuth to selected DX |
| **Faros** | NCDXF/IARU beacon monitor | **Beacon clock**: live NCDXF schedule (18 beacons × 5 bands, 3-min cycle) with one-click QSY to listen |
| **DX Bulletin Reader** | Reads 425DXN bulletins | **DXpedition calendar** panel: current/announced operations with dates, bands, modes |
| Ham Cockpit | Plugin dashboard host | The single-page dashboard itself is the modern equivalent |
| RTTY Skimmer, GRITTY | RTTY | **Ignored** — not CW/FT8 |
| Voice Shaper | SSB audio | **Ignored** — not CW/FT8 |
| Rocky, HamVNA, Afedri tools, SkyRoof, Morse MIDI, enigma-cuda, etc. | SDR/VNA/satellite/misc | **Ignored** — not directly DX-chasing for CW/FT8 |

## 2. Users and primary scenarios

**User:** an HF operator chasing a DXpedition on CW and FT8 (typically Fox/Hound).

1. **"Is the DXpedition on, and where?"** — Spots stream in; the DXpedition's calls are pinned
   at the top; one click tunes the radio, sets the right mode, and pre-sets split from the
   spot comment (`UP 2`, `QSX 14023.5`).
2. **"What can I work that I still need?"** — Every spot is resolved to a DXCC entity and
   compared with the operator's log (ADIF import): all-time-new-ones, new band slots and new
   mode slots are colour-flagged and can be filtered ("needed only").
3. **"Is the band open there?"** — Solar panel, band-condition summary, gray-line map with
   terminator (gray-line enhancement is prime DX time), NCDXF beacon clock to check a path by ear.
4. **"FT8 F/H flow"** — WSJT-X runs alongside; the dashboard mirrors its decodes, highlights
   the DX and needed calls, and a double-click sends a WSJT-X *Reply* packet to start calling.
5. **"Be ready for the pileup"** — CW Pileup Trainer generates a multi-station pileup in the
   browser; copy calls under QRM before doing it for real.

## 3. Functional requirements

### 3.1 Rig control (OmniRig)
- FR-1 Connect to `OmniRig.OmniRigX` COM server; select Rig 1 or Rig 2; surface `StatusStr`
  (On-line / Rig is not responding / Port busy / ...).
- FR-2 Poll and display: VFO A/B frequency, mode, split state, TX state (≤ 500 ms latency).
- FR-3 Set frequency, set mode (CW ⇄ DATA-U/USB for FT8), set simplex (`SetSimplexMode`) and
  split (`SetSplitMode(rx, tx)`).
- FR-4 **Click-to-tune** from any spot, decode, beacon or band-map marker: frequency + correct
  mode + split offset when the spot indicates one.
- FR-5 If OmniRig is not installed/available, degrade gracefully to the **simulated rig** and
  say so in the UI.

### 3.2 DX cluster spots
- FR-6 Telnet client to any DX cluster node (default configurable; works with DXSpider, AR-Cluster,
  CC Cluster, VE3NEA's PskrDxClusterService). Login with the operator's callsign; auto-reconnect
  with backoff.
- FR-7 Parse standard `DX de SPOTTER: freq DXCALL comment HHMMZ` lines; tolerate real-world
  formatting variance.
- FR-8 Classify each spot: band (160–6 m), mode (CW / FT8 / FT4 / SSB / RTTY / OTHER) using
  comment keywords first, then digital-window frequencies, then CW sub-band position.
- FR-9 Extract split hints from comments: `UP n`, `DN n`, `QSX freq`.
- FR-10 Resolve DXCC entity (name, prefix, continent, CQ zone, lat/lon) via `cty.dat`
  (auto-downloaded from country-files.com; bundled fallback subset). Compute short-path
  azimuth and distance from the operator's grid square.
- FR-11 Spot store: dedupe (same call ±1 kHz within 10 min refreshes rather than duplicates),
  age-out (default 30 min), cap (2000).
- FR-12 Filters: band, mode (CW/FT8/FT4 one click), continent, "needed only", text search.
  A **watch list** (DXpedition callsigns) pins matching spots and fires an alert
  (visual + optional audio).

### 3.3 Band map
- FR-13 Vertical frequency ladder for the selected band, CW segment and FT8/FT4 windows shaded,
  spots plotted at their frequency with age fading, current rig frequency as a moving cursor,
  click anywhere → QSY, click a spot → full tune (mode/split).

### 3.4 DXCC needed tracking
- FR-14 Import the operator's log from **ADIF** (`.adi`) to build worked/confirmed state per
  entity × band × mode.
- FR-15 Classify every spot/decode: **ATNO** (all-time new one), **new band**, **new mode-slot**,
  or worked; colour-coded everywhere (table, band map, world map).

### 3.5 Propagation & beacons
- FR-16 Solar panel: SFI, sunspots, A, K, X-ray, aurora, updated ≤ 30-min intervals from
  hamqsl.com XML; per-band day/night condition summary.
- FR-17 NCDXF/IARU beacon clock: pure-time computation of the 18-beacon × 5-band schedule
  (10 s slots, 180 s cycle); shows who transmits **now** on 14.100/18.110/21.150/24.930/28.200;
  click → tune (CW mode). Doubles as a live propagation probe (Faros heritage).
- FR-18 Gray-line world map: equirectangular map, live solar terminator + sun position, spot
  markers coloured by mode/needed status, great-circle path to the selected spot, home QTH marker.

### 3.6 FT8/FT4 (WSJT-X integration)
- FR-19 Listen on the WSJT-X UDP port (default 2237): Heartbeat, Status, Decode, QSOLogged.
- FR-20 Live decode stream with callsign/DXCC resolution and needed-status colour; CQ lines
  highlighted; the current DX call from WSJT-X Status shown.
- FR-21 Double-click a decode → send a WSJT-X **Reply** packet (starts calling that station in
  WSJT-X). QSOLogged updates the needed-tracker immediately.

### 3.7 CW Pileup Trainer (Morse Runner heritage)
- FR-22 Browser-side Web-Audio CW pileup: 1–4 stations calling simultaneously with random
  valid-format callsigns, independent pitch (400–900 Hz), speed (22–38 WPM) and level;
  operator types the call, correct copy answers with an exchange; running score and accuracy.
  Difficulty presets. Works fully offline.

### 3.8 DXpedition calendar
- FR-23 Panel of current + announced DXpeditions (dates, entity, bands/modes, callsign);
  refreshed from NG3K ADXO when online, bundled snapshot otherwise; one click adds the
  callsign to the watch list.

### 3.9 General / non-functional
- FR-24 Single-page app served locally (`http://localhost:8073`), dark theme, live UTC clock,
  usable at 1366×768 and up. No build toolchain — plain HTML/CSS/JS, no CDN required for
  core function (world-map coastlines fetched once, cached, optional).
- FR-25 All state pushed over one WebSocket; commands via REST. UI reconnects automatically.
- FR-26 **Demo mode**: one flag switches every source to simulators (rig, cluster, WSJT-X,
  solar) — the full dashboard runs with zero hardware, zero internet, for testing and demos.
- FR-27 Config in `config.json` (callsign, grid, cluster host, rig number, ports, watch list).
  Persistent data (log state, cached cty.dat, settings) under `data/`.

## 4. Architecture

```
┌────────────────────────── Browser (single page) ──────────────────────────┐
│ Rig panel │ Band map │ Spot table │ World map │ Solar │ Beacons │ FT8 │ CW │
└──────▲───────────────────────────────▲───────────────────────────────────┘
       │ REST (commands)               │ WebSocket (state stream)
┌──────┴───────────────────────────────┴───────────────────────────────────┐
│                       FastAPI + uvicorn (Python 3.11)                     │
│  EventBus ── broadcasts JSON frames to all sockets                        │
│  ├─ RigService      ── OmniRigBackend (COM, own STA thread)  ─┐           │
│  │                   └ SimulatedRig                           ├ pluggable │
│  ├─ SpotService     ── ClusterClient (telnet, asyncio)        │           │
│  │                   └ SpotSimulator (DXpedition scenario)   ─┘           │
│  ├─ DxccService     ── cty.dat parser, ADIF import, needed tracker        │
│  ├─ PropagationSvc  ── hamqsl solar fetch │ NCDXF beacon schedule         │
│  ├─ WsjtxService    ── UDP listener/encoder │ WSJT-X simulator            │
│  └─ DxpedService    ── NG3K fetch │ bundled snapshot                      │
└───────────────────────────────────────────────────────────────────────────┘
```

- **OmniRig thread**: COM requires an STA thread; the backend pins one thread, polls at 300 ms,
  and marshals commands via a queue. All other I/O is asyncio.
- **Simulation-first design**: every external dependency (rig, cluster, WSJT-X, solar) has a
  simulator behind the same interface — this is the test harness *and* the demo.

## 5. Out of scope (v1)
Wideband DSP decoding (CW Skimmer/JTSkimmer's core), VOACAP point-to-point prediction, logging
(the dashboard reads logs, it does not replace the logger), RTTY/SSB features, LoTW/Clublog
sync, multi-user server operation.

## 6. Acceptance criteria (summary)
1. `run_demo.bat` → dashboard fully alive with simulated rig + spots + FT8 within 5 s.
2. Click a simulated CW spot with `UP 2` → rig shows split RX/TX 2 kHz apart, mode CW.
3. ADIF import → needed flags change accordingly; "needed only" filter works.
4. Beacon clock matches the published NCDXF schedule for the current UTC time (unit-tested).
5. With OmniRig installed and a rig (or rig emulator) attached: frequency/mode round-trip
   works from the real radio (operator smoke-test checklist in README).
6. `pytest` suite green.
