# DX Command — Build & Test Plan

## Phases

| # | Phase | Deliverable |
|---|---|---|
| 1 | Specification | `SPEC.md` (this repo) |
| 2 | Backend core | FastAPI app, EventBus, config, rig abstraction + **simulated rig**, OmniRig COM backend |
| 3 | Spot pipeline | Telnet cluster client, spot parser/classifier, store, **DXpedition scenario simulator** |
| 4 | DXCC engine | cty.dat parser (auto-download + bundled fallback), ADIF import, needed tracker |
| 5 | Propagation | hamqsl solar fetch (+canned demo data), NCDXF beacon schedule engine |
| 6 | WSJT-X | UDP protocol codec (Heartbeat/Status/Decode/QSOLogged/Reply), listener, **FT8 simulator** |
| 7 | Frontend | Single-page dashboard: rig panel, band map, spot table, world map w/ gray line, side panels, CW pileup trainer |
| 8 | Tests | pytest unit suite over all pure logic; simulators as integration harness |
| 9 | Verification | Live browser run in demo mode; scripted checks (tune round-trip, filters, beacons) |
| 10 | Packaging | README (install + operator smoke-test checklist), run scripts, distributable zip |

## Testing strategy

**1. Unit tests (pytest)** — all logic that doesn't need hardware:
- `test_cty.py` — cty.dat parsing: prefixes, exact `=CALL` overrides, zone overrides, longest-prefix matching (K1ABC→USA, JA7X→Japan, 3Y0K→Bouvet, VP8…)
- `test_spot_parser.py` — real-world cluster line formats; band/mode classification (comment beats frequency; FT8 windows; CW sub-band); split-hint extraction (`UP 2`, `QSX 14023.5`)
- `test_store.py` — dedupe/refresh, age-out, cap
- `test_beacons.py` — NCDXF schedule invariants: t=0 → 4U1UN on 14.100; each slot exactly one beacon per band; 180 s wrap
- `test_adif_tracker.py` — ADIF parse; ATNO / new-band / new-mode classification transitions
- `test_wsjtx.py` — binary codec round-trip: parse synthetic Decode/Status packets, encode Reply and re-parse
- `test_rig_sim.py` — simulated rig: tune, mode, split semantics match the OmniRig-shaped interface

**2. Simulation integration (the "radio simulator" requirement)** — demo mode wires
SimulatedRig + SpotSimulator (a scripted DXpedition scenario with pileups, split comments,
needed entities) + WSJT-X simulator (15 s FT8 cycles of realistic decodes) into the real
services. Anything that works in demo mode exercises the same code paths as production
except the COM/telnet/UDP edges.

**3. Live browser verification** — run demo mode, drive the UI: spots stream, click-to-tune
updates the rig panel (split honoured), filters, needed highlighting after ADIF import,
beacon clock ticks, terminator renders.

**4. Operator hardware smoke test (in README)** — for the radio operator with a real rig:
OmniRig install → rig online → frequency/mode/split round-trip → cluster login →
WSJT-X UDP hookup → one real click-to-tune on a spotted station.

## Key design decisions
- **Python 3.11 + FastAPI**, plain-JS frontend, no build step → trivially shareable and hackable.
- **COM via pywin32 on a dedicated STA thread** — OmniRig's documented usage pattern; the rest of the app stays asyncio.
- **Every external edge has a simulator** behind the same interface — testability without hardware was a hard requirement.
- Default port **8073** (unassigned, memorable: 80 + "73").
