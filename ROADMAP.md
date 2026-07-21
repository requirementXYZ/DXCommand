# DX Command — Roadmap

**Update (v1.5.0, 2026-07-21): all P1 and P2 items below SHIPPED** — alerting engine,
DXpedition slot matrix, RBN feed with spotted-by-continent, log auto-sync with
LoTW-confirmed tracking, gray-line time scrubber, SQLite spot persistence with
activity timelines, band-openings strip, and the one-file Windows build
(`build_exe.bat` / release exe). P3 and exploratory items remain open for a
future release.

Original proposal (kept for context). Priorities are ranked by
value to the target operator: a CW/FT8 DXer trying to put a DXpedition in the log.
Effort is a rough guide (S = a session, M = a few sessions, L = a mini-project).

## The lens used for prioritising

The dashboard already answers *"what is on right now and how do I tune to it?"*
The biggest remaining gaps, in operator terms:

1. *"Tell me the moment my target appears — I can't sit and watch."* (alerting)
2. *"What do I still need from THIS DXpedition, and where are they right now?"* (slot matrix)
3. *"Can I actually hear/work them from my QTH?"* (RBN, spotted-by-region)
4. *"Don't make me re-import my log every day."* (log auto-sync)

---

## P1 — proposed core of v1.5

### 1. Alerting engine (highest value)
Browser/desktop notifications + audio, driven by rules — not just toasts you have to
be watching. Rule fields: watch-list call, needed level (ATNO / band / mode), band,
mode, continent-of-spotter ("alert only if heard in my region"). Per-rule sound;
quiet hours; a small "alert log" panel so a missed alert can be reviewed.
*Why first: a DXpedition window can be 10 minutes long; the tool's job is to fetch
the operator to the radio.* — **Effort M**

### 2. DXpedition slot matrix (Club Log-style)
Click a DXpedition → a band × mode grid showing: needed / worked / confirmed for
that entity from your log, overlaid with where the operation has actually been
spotted (last hour / last day), with click-to-tune on any active slot.
This is *the* view a chaser wants open all week.
*Heritage: Club Log's DXpedition charts; Band Master's "needed" logic taken further.*
— **Effort M**

### 3. Reverse Beacon Network direct feed + "who hears them"
Connect to `telnet.reversebeacon.net:7000` as a second spot source (same telnet
protocol; skimmer format parsing is a small parser extension). Merge with cluster
spots and keep the *spotter list* per DX instead of only the latest: show SNR and
which continents are hearing them. A "heard in <your continent>" badge on each spot
answers the real question — is the band open *to me*?
*Heritage: CW Skimmer/RBN — VE3NEA's skimmer network output, consumed properly.*
— **Effort M**

### 4. Log auto-sync (watch ADIF files)
Watch configured log files for changes (e.g. WSJT-X `wsjtx_log.adi`, DXKeeper/Log4OM
ADIF export path) and re-import automatically, so needed-flags stay truthful without
manual imports. Include LoTW-report import so **confirmed** vs merely **worked** is
tracked (ATNO chasing usually means *confirmed* matters).
— **Effort S/M**

## P2 — strong candidates, next after P1

5. **Gray-line time scrubber** — drag a time slider to see the terminator at any
   hour; highlight when your QTH and the DX share gray line ("best low-band window
   ≈ 0510–0540Z"). *DX Atlas heritage.* — **Effort S/M**
6. **Spot persistence + activity timeline** — SQLite spot history surviving
   restarts; per-DX timeline strip (which band, when) to reveal the operation's
   schedule pattern ("they do 30 m CW around 0300Z"). — **Effort M**
7. **Windows one-file build** — PyInstaller `.exe` so testers don't need Python
   installed; biggest single distribution-friction remover. — **Effort S/M**
8. **Band-openings summary** — per-band spot-rate by continent over the last hour
   ("10 m open to EU, 15 m dead") as a compact strip above the spot table. — **Effort S**

## P3 — worthwhile, not urgent

9. **CW trainer expansion** — exchange copying (599 + serial), QSB/QRN/QRM options,
   pileup depth ramping, session history/high scores (full Morse Runner parity).
10. **LAN/tablet access** — bind option beyond localhost with a simple token, plus a
    responsive layout for a tablet in the shack.
11. **Lightweight path scoring** — day/night + solar-index heuristic per spot path
    (a "mini-HamCAP" hint, not full VOACAP), shown as a small open/marginal/closed dot.
12. **UI polish pack** — resizable/hideable panels, font-size control, light theme.

## Exploratory (flagged, no commitment)

- **In-browser CW decoder** on rig audio via WebAudio (DeepCW/CW Skimmer heritage) —
  high wow-factor, high effort, uncertain accuracy; prototype only after P1/P2.
- **Rotator control** (azimuth click-to-turn) — valuable for the beam-equipped
  minority; depends on picking a rotator protocol (PSTRotator, GS-232).
- **Multi-rig SO2R view** — OmniRig exposes Rig 1+2 simultaneously; niche.

## Suggested v1.5 scope

P1 items 1–4. They share plumbing (rule engine touches spots+decodes; RBN reuses the
cluster client; slot matrix reuses tracker + spot store) and together they convert
the dashboard from "information display" into "an assistant that gets you the ATNO".

---
*Comments welcome — annotate this file or open a GitHub issue per item.*
