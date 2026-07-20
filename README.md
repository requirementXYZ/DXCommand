# DX Command 📡

**A modern web dashboard for CW and FT8 operators chasing DXpeditions.**

DX Command re-imagines the classic VE3NEA / DX Atlas tool family (Band Master, OmniRig,
Morse Runner, Faros, DX Atlas, the WSJT-X ecosystem) as one dark-themed browser
dashboard that talks to **any radio supported by OmniRig**.

| | |
|---|---|
| Live DX spots | Telnet cluster client, CW/FT8/FT4 classification, split-comment parsing (`UP 2`, `QSX …`) |
| Click-to-tune | One click sets frequency **and mode and split** on your rig via OmniRig |
| Band map | Vertical ladder per band, CW/FT8 segments shaded, rig cursor, click to QSY |
| Needed DXCC | Import your log (ADIF) — ATNO / new-band / new-mode flags on every spot & decode |
| WSJT-X | Live decode mirror with DXCC + needed colouring; double-click a decode → WSJT-X starts calling |
| Gray line | World map with live solar terminator, spot markers, great-circle path + azimuth |
| NCDXF beacons | Live 18-beacon schedule clock; click to listen (Faros heritage) |
| Solar data | SFI / SSN / A / K / X-ray + band conditions (hamqsl.com) |
| DXpeditions | Current & announced operations; one click adds to the alert watch list |
| CW Pileup Trainer | Morse Runner-style multi-station pileup in the browser (Web Audio, works offline) |
| **Demo mode** | Full simulation of rig + cluster + WSJT-X — try everything with **no radio and no internet** |

---

## Installation

1. Install [Python 3.11+](https://www.python.org/downloads/) (tick *"Add python to PATH"*).
2. Get the code — either:
   ```
   git clone https://github.com/requirementXYZ/DXCommand.git
   cd DXCommand
   ```
   or on GitHub use **Code → Download ZIP** and extract it anywhere.
3. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```

Runs on Windows 10/11. OmniRig (for real rig control) and WSJT-X are optional —
everything can be tried first in demo mode.

## Quick start (no radio needed)

Double-click **`run_demo.bat`** and open **http://localhost:8073**.

You get a fully working dashboard against a simulated radio, a simulated DX cluster
running a Bouvet DXpedition pileup, and simulated WSJT-X Fox/Hound traffic. Click spots,
watch the split light up, try the CW trainer.

## Going live with your radio

All station settings live in the dashboard itself — click **⚙ SETUP** (top right):

- **Callsign / grid** — used for cluster login, azimuths and the map.
- **Radio** — *Demo (simulated rig)* or *OmniRig Rig 1 / Rig 2*.
- **DX spots** — *Demo feed* or a real telnet cluster (host/port).
- **FT8 decodes** — *Demo*, *WSJT-X UDP listener*, or off.

Changes apply immediately (no restart) and persist to `config.json`.
The 🧪 **ALL DEMO** / 📡 **ALL LIVE** buttons switch everything at once.

Prerequisites for live operation:

1. Install **OmniRig** from https://dxatlas.com/omnirig/ and configure your rig
   (COM port, baud rate). Icom users: turn **CI-V Transceive OFF** in the radio.
2. If you run WSJT-X: *File → Settings → Reporting →* UDP Server `127.0.0.1`,
   port `2237` (defaults). DX Command listens on the same port.
   > If another program (GridTracker, JTAlert) already claims port 2237, use
   > WSJT-X *secondary* UDP or change the port in ⚙ SETUP.
3. Double-click **`run.bat`** and open **http://localhost:8073**.

`run_demo.bat` always forces full simulation regardless of saved settings;
`run.bat` honours whatever you last saved in ⚙ SETUP.

### Operator smoke-test checklist (10 minutes)

1. **Rig link** — header chip `RIG ●` green; turn the VFO: the dashboard frequency
   follows within ½ s. Change mode on the radio: dashboard follows.
2. **QSY from dashboard** — type `14023.5` in the QSY box → radio moves; press a band
   button → radio moves to the CW segment of that band.
3. **Split** — click a CW spot whose comment says `UP …`: radio should go split with
   TX offset shown in the orange SPLIT tag. Click an FT8 spot: split clears, mode DATA.
4. **Cluster** — chip `CLUSTER ●` green and spots streaming within ~30 s of start.
5. **Needed flags** — Import ADIF (top right) with your log export; worked slots lose
   their ★, "Needed only" filter shows the rest.
6. **WSJT-X** — with WSJT-X decoding, decodes appear in the right panel; double-click
   a CQ → WSJT-X sets that DX call and (with Enable Tx armed) starts calling.
7. **Beacons** — at hh:mm:00 with minutes divisible by 3, 14.100 shows 4U1UN
   (published NCDXF schedule). Click a beacon row and listen.

Anything off? Note the step number and send back console output from the black window.

## Configuration reference (`config.json`)

```jsonc
{
  "callsign": "N0CALL",          // used for cluster login
  "grid": "FN31pr",              // your Maidenhead locator (azimuth/distance/map)
  "port": 8073,                  // web UI port
  "demo_mode": false,            // true = all simulators (or use run_demo.bat)
  "rig":     { "backend": "omnirig", "rig_number": 1, "poll_ms": 300 },
  "cluster": { "host": "dxc.ve7cc.net", "port": 23,
               "keep_modes": ["CW", "FT8", "FT4"] },   // drop SSB/RTTY spots
  "wsjtx":   { "enabled": true, "udp_port": 2237 },
  "spots":   { "max_age_min": 30, "max_count": 2000 },
  "watch_list": ["3Y0K"]         // calls that always alert & pin
}
```

Tip: point `cluster.host` at a local instance of VE3NEA's
[PskrDxClusterService](https://github.com/VE3NEA/PskrDxClusterService)
(`localhost:7309`) for a very dense FT8 spot feed from PSK Reporter.

- `data/cty.dat` — full AD1C country file, auto-downloaded on first online start
  (bundled subset used offline). Delete the file to force a refresh.
- `data/worked.json` — your worked-slot state (rebuilt any time from ADIF import).
- `data/dxpeditions.json` — optional: maintain your own DXpedition list here.

## Tests

```
python -m pytest tests -q
```

65+ unit tests cover the cty.dat parser, spot parser/classifier, spot store,
NCDXF beacon schedule, ADIF import & needed-tracking, the WSJT-X binary protocol
(round-trip), and the simulated rig. The demo mode doubles as the integration
harness: it exercises every code path except the COM/telnet/UDP edges themselves.

## Architecture (short version)

Python 3.11 · FastAPI · one WebSocket for state, REST for commands · plain
HTML/CSS/JS frontend, no build step. OmniRig is driven over COM from a dedicated
STA thread; every external dependency (rig, cluster, WSJT-X, solar) has a
simulator behind the same interface. See `SPEC.md` and `PLAN.md` for the full
specification and heritage analysis.

## Credits

Functional heritage: Alex Shovkoplyas VE3NEA's outstanding freeware
(https://dxatlas.com, https://github.com/VE3NEA) — Band Master, OmniRig,
CW Skimmer, Morse Runner, Faros, HamCAP, DX Atlas. Solar data by Paul Herrman
N0NBH (hamqsl.com). Country data by Jim Reisert AD1C (country-files.com).
DXpedition data: Bill Feidt NG3K (ADXO). This project is an independent
re-imagining, not affiliated with any of the above.

*73 and good DX!*
