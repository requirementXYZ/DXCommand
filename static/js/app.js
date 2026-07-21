"use strict";
/* Main application: state, websocket wiring, spot table, panels. */

const state = {
  spots: new Map(),          // id -> spot
  filters: { bands: new Set(), modes: new Set(["CW", "FT8", "FT4"]),
             neededOnly: false, search: "" },
  watch: [],
  rig: null,
  myCont: "NA",
};

const bus = new Bus();
const bandmap = new BandMap($("bandmap"), (spot) => tuneSpot(spot));
const worldmap = new WorldMap($("worldmap"), (s) => tuneSpot(s));
const cwtrainer = new CwTrainer();

/* ---------------- clock ---------------- */
setInterval(() => {
  const d = new Date();
  $("utc-clock").firstChild.textContent =
    [d.getUTCHours(), d.getUTCMinutes(), d.getUTCSeconds()]
      .map((n) => String(n).padStart(2, "0")).join(":");
}, 250);

/* ---------------- tune ---------------- */
async function tuneSpot(spot) {
  const body = { freq_khz: spot.freq };
  if (spot.mode) body.mode = spot.mode;
  if (spot.split_tx_khz) body.split_tx_khz = spot.split_tx_khz;
  await post("/api/rig/tune", body);
  const split = spot.split_tx_khz ? ` split TX ${fmtFreqKhz(spot.split_tx_khz)}` : "";
  toast(`QSY ${fmtFreqKhz(spot.freq)}${spot.mode ? " " + spot.mode : ""}${split}` +
        (spot.dx_call ? ` → ${spot.dx_call}` : ""));
  if (spot.dxcc) { worldmap.selected = spot; worldmap.draw(); }
}

/* ---------------- rig panel ---------------- */
bus.on("rig", (r) => {
  state.rig = r;
  const khz = r.freq / 1000;
  const mhz = Math.floor(khz / 1000);
  $("freq-mhz").textContent = `${mhz}.${String(Math.floor(khz % 1000)).padStart(3, "0")}`;
  $("freq-hz").textContent = String(Math.round((khz % 1) * 1000)).padStart(3, "0");
  $("rig-mode").textContent = r.mode;
  $("rig-split").hidden = !r.split;
  if (r.split) {
    const off = (r.tx_freq - r.freq) / 1000;
    $("split-offset").textContent = (off >= 0 ? "+" : "") + off.toFixed(1);
  }
  $("rig-tx").hidden = !r.tx;
  $("rig-status-text").textContent = r.status;
  $("rig-label").textContent = r.label;
  setChip("chip-rig", r.online, r.online ? "RIG ●" : "RIG ○");
  bandmap.setRig(khz);
});

function setChip(id, ok, text, warn) {
  const el = $(id);
  el.className = "chip " + (ok ? "ok" : warn ? "warn" : "");
  if (text) el.textContent = text;
}

/* band + mode buttons */
const BANDS_UI = ["160m", "80m", "40m", "30m", "20m", "17m", "15m", "12m", "10m", "6m"];
const BAND_CENTER_CW = { "160m": 1822, "80m": 3515, "40m": 7015, "30m": 10110,
  "20m": 14025, "17m": 18075, "15m": 21025, "12m": 24895, "10m": 28025, "6m": 50095 };
for (const b of BANDS_UI) {
  const btn = document.createElement("button");
  btn.textContent = b.replace("m", "");
  btn.title = b;
  btn.onclick = () => {
    post("/api/rig/freq", { freq_hz: BAND_CENTER_CW[b] * 1000 });
    bandmap.setBand(b);
  };
  $("band-buttons").appendChild(btn);
}
document.querySelectorAll(".mode-buttons button").forEach((btn) => {
  btn.onclick = () => post("/api/rig/mode", { mode: btn.dataset.mode });
});
$("qsy-go").onclick = () => {
  const khz = parseFloat($("qsy-input").value);
  if (khz > 1000) post("/api/rig/freq", { freq_hz: Math.round(khz * 1000) });
};
$("qsy-input").addEventListener("keydown", (e) => { if (e.key === "Enter") $("qsy-go").click(); });

/* ---------------- filters ---------------- */
for (const b of ["ALL", ...BANDS_UI]) {
  const btn = document.createElement("button");
  btn.className = "fbtn" + (b === "ALL" ? " active" : "");
  btn.textContent = b === "ALL" ? "All" : b.replace("m", "");
  btn.dataset.band = b;
  btn.onclick = () => {
    if (b === "ALL") state.filters.bands.clear();
    else state.filters.bands.has(b) ? state.filters.bands.delete(b)
                                    : state.filters.bands.add(b);
    document.querySelectorAll("#filter-bands .fbtn").forEach((x) =>
      x.classList.toggle("active",
        x.dataset.band === "ALL" ? state.filters.bands.size === 0
                                 : state.filters.bands.has(x.dataset.band)));
    renderSpots();
  };
  $("filter-bands").appendChild(btn);
}
document.querySelectorAll("#filter-modes .fbtn").forEach((btn) => {
  btn.onclick = () => {
    const m = btn.dataset.mode;
    state.filters.modes.has(m) ? state.filters.modes.delete(m) : state.filters.modes.add(m);
    btn.classList.toggle("active", state.filters.modes.has(m));
    renderSpots();
  };
});
$("filter-needed").onclick = () => {
  state.filters.neededOnly = !state.filters.neededOnly;
  $("filter-needed").classList.toggle("active", state.filters.neededOnly);
  renderSpots();
};
$("filter-search").addEventListener("input", (e) => {
  state.filters.search = e.target.value.toUpperCase();
  renderSpots();
});

/* ---------------- spots ---------------- */
function spotVisible(s) {
  const f = state.filters;
  if (f.bands.size && !f.bands.has(s.band)) return false;
  const m = ["CW", "FT8", "FT4"].includes(s.mode) ? s.mode : "OTHER";
  if (!f.modes.has(m)) return false;
  if (f.neededOnly && !s.needed && !s.watched) return false;
  if (f.search && !(s.dx_call.includes(f.search) ||
      (s.dxcc && s.dxcc.name.toUpperCase().includes(f.search)))) return false;
  return true;
}

function spotRow(s, fresh) {
  const tr = document.createElement("tr");
  tr.className = (s.needed ? `needed-${s.needed} ` : "") +
                 (s.watched ? "watched " : "") + (fresh ? "fresh" : "");
  const star = { atno: "★ATNO", band: "★band", mode: "★mode" }[s.needed] || "";
  const conts = s.heard_conts || [];
  const heardHome = conts.includes(state.myCont);
  const heardTitle = (s.spotters || []).map((sp) =>
    `${sp.call}${sp.cont ? " (" + sp.cont + ")" : ""}${sp.snr != null ? " " + sp.snr + "dB" : ""}`
  ).join(", ");
  tr.innerHTML =
    `<td class="dim">${utcHHMM(s.ts)}</td>` +
    `<td class="freq">${fmtFreqKhz(s.freq)}</td>` +
    `<td class="call">${esc(s.dx_call)}<span class="needed-star">${star}</span></td>` +
    `<td><span class="mchip ${esc(s.mode)}">${esc(s.mode)}</span></td>` +
    `<td>${esc(s.dxcc ? s.dxcc.name : "?")}</td>` +
    `<td class="r dim">${s.dxcc ? s.dxcc.azimuth : ""}</td>` +
    `<td class="heard${heardHome ? " home" : ""}" title="${esc(heardTitle)}">` +
    `${esc(conts.slice(0, 3).join("·"))}${s.snr != null ? " " + s.snr + "dB" : ""}</td>` +
    `<td class="dim">${esc(s.comment || "")}</td>` +
    `<td class="r dim">${fmtAge(Math.floor(Date.now() / 1000 - s.ts))}</td>`;
  tr.onclick = () => tuneSpot(s);
  return tr;
}

let renderPending = false;
function renderSpots() {
  if (renderPending) return;
  renderPending = true;
  setTimeout(() => {   // not rAF: must also work in throttled/background tabs
    renderPending = false;
    const spots = [...state.spots.values()].sort((a, b) => b.ts - a.ts);
    const tbody = $("spot-tbody");
    tbody.replaceChildren();
    let shown = 0;
    for (const s of spots) {
      if (!spotVisible(s)) continue;
      tbody.appendChild(spotRow(s));
      if (++shown >= 300) break;
    }
    $("spot-count").textContent = `${shown} / ${spots.length} spots`;
    bandmap.setSpots(spots.filter(spotVisible));
    worldmap.spots = spots.filter(spotVisible);
    worldmap.draw();
    renderOpenings(spots);
  }, 80);
}

/* Band openings: spot activity per band in the last 30 min, by DX continent */
function renderOpenings(spots) {
  const per = {};
  for (const s of spots) {
    if (!s.band) continue;
    const p = (per[s.band] = per[s.band] || { n: 0, conts: new Set() });
    p.n++;
    if (s.dxcc) p.conts.add(s.dxcc.cont);
  }
  const strip = $("openings-strip");
  strip.replaceChildren();
  for (const b of BANDS_UI) {
    const p = per[b];
    const chip = document.createElement("span");
    chip.className = "open-chip" + (p ? " hot" : "") +
      (state.filters.bands.has(b) ? " filtered" : "");
    chip.innerHTML = p ? `${b} <b>${p.n}</b> ${[...p.conts].sort().join("·")}` : b;
    chip.onclick = () => {
      const target = document.querySelector(`#filter-bands .fbtn[data-band="${b}"]`);
      if (target) target.click();
    };
    strip.appendChild(chip);
  }
}

bus.on("spot", (s) => {
  state.spots.set(s.id, s);
  if (s.watched && Date.now() / 1000 - s.ts < 120) {
    toast(`⚑ ${s.dx_call} spotted on ${fmtFreqKhz(s.freq)} ${s.mode}`, "alert");
  }
  renderSpots();
});

async function loadSpots() {
  const spots = await (await fetch("/api/spots")).json();
  state.spots.clear();
  for (const s of spots) state.spots.set(s.id, s);
  renderSpots();
}
setInterval(renderSpots, 15000); // refresh ages

/* ---------------- cluster / app info ---------------- */
bus.on("cluster_status", (s) => {
  const ok = /connected|logged in|simulated/.test(s.text);
  setChip("chip-cluster", ok, "CLUSTER " + (ok ? "●" : "○"));
  $("chip-cluster").title = s.text;
});
bus.on("app_info", (info) => {
  $("my-call").textContent = info.callsign;
  $("my-grid").textContent = info.grid;
  $("demo-badge").hidden = !info.demo;
  worldmap.home = { ...info.home, call: info.callsign, grid: info.grid };
  state.watch = info.watch_list;
  state.myCont = info.my_continent || "NA";
  Alerts.applyConfig(info.alerts);
  renderWatch();
});
bus.on("alert", (a) => Alerts.onAlert(a));
bus.on("rbn_status", (s) => { $("chip-cluster").title += ` | RBN: ${s.text}`; });
bus.on("log_sync", (r) => {
  toast(`📖 Log synced (${r.file}): ${r.qsos} QSOs, +${r.slots_added} slots`);
  loadSpots();
});

/* ---------------- solar ---------------- */
bus.on("solar", (d) => {
  $("sfi").textContent = d.sfi;
  $("ssn").textContent = d.sunspots;
  $("a-idx").textContent = d.a_index;
  $("k-idx").textContent = d.k_index;
  $("solar-src").textContent = d.source;
  $("solar-extra").textContent = `X-ray ${d.xray || "-"} • aurora ${d.aurora ?? "-"} • ${d.updated || ""}`;
  const rows = (d.bands || []).map((b) =>
    `<tr><td>${b.name}</td><td class="cond-${b.day}">${b.day}</td>` +
    `<td class="cond-${b.night}">${b.night}</td></tr>`).join("");
  $("cond-table").innerHTML =
    `<tr><td class="dim"></td><td class="dim">day</td><td class="dim">night</td></tr>` + rows;
});

/* ---------------- beacons ---------------- */
bus.on("beacons", (list) => {
  worldmap.beacons = list;
  const wrap = $("beacon-list");
  wrap.replaceChildren();
  for (const b of list) {
    const row = document.createElement("div");
    row.className = "beacon-row";
    row.title = `tune ${fmtFreqKhz(b.freq)} CW`;
    row.innerHTML =
      `<span class="beacon-freq">${(b.freq / 1000).toFixed(3)}</span>` +
      `<span class="beacon-call">${b.call}</span>` +
      `<span class="beacon-loc">${b.location}</span>` +
      `<span class="beacon-bar"><i style="width:${b.slot_remaining_s * 10}%"></i></span>`;
    row.onclick = () => tuneSpot({ freq: b.freq, mode: "CW", dx_call: b.call });
    wrap.appendChild(row);
  }
});

/* ---------------- dxpeditions ---------------- */
bus.on("dxped", (d) => {
  $("dxped-src").textContent = d.source || "";
  const wrap = $("dxped-list");
  wrap.replaceChildren();
  for (const it of d.items || []) {
    const row = document.createElement("div");
    row.className = "dxped-row";
    row.title = "click for slot matrix: what you need from this one";
    row.innerHTML = `<b>${esc(it.callsign)}</b> ${esc(it.entity)}<div class="small">` +
      `${esc(it.start)} → ${esc(it.end)}  ${esc(it.bands || "")} ${esc(it.modes || "")}</div>`;
    row.onclick = () => Matrix.open(it.callsign);
    wrap.appendChild(row);
  }
});

/* ---------------- watch list ---------------- */
function renderWatch() {
  const wrap = $("watch-list");
  wrap.replaceChildren();
  for (const c of state.watch) {
    const el = document.createElement("span");
    el.className = "watch-item";
    el.innerHTML = `${c} <b title="remove">✕</b>`;
    el.querySelector("b").onclick = () => post("/api/watch", { call: c, remove: true });
    wrap.appendChild(el);
  }
}
async function addWatch(call) {
  if (!call) return;
  const r = await post("/api/watch", { call });
  toast(`Watching ${call.toUpperCase()}`);
  state.watch = r.watch_list;
  renderWatch();
  loadSpots();
}
bus.on("watch_list", (list) => { state.watch = list; renderWatch(); loadSpots(); });
bus.on("tracker_stats", () => loadSpots());   // needed flags changed server-side
$("watch-add").onclick = () => { addWatch($("watch-input").value.trim()); $("watch-input").value = ""; };
$("watch-input").addEventListener("keydown", (e) => { if (e.key === "Enter") $("watch-add").click(); });

/* ---------------- WSJT-X ---------------- */
const ft8Rows = [];
bus.on("wsjtx_decode", (d) => {
  const row = document.createElement("div");
  row.className = "ft8-row" + (d.cq ? " cq" : "") +
    (d.needed ? ` needed-${d.needed}` : "") + (d.watched ? " watched" : "");
  row.innerHTML =
    `<span class="dim">${String(Math.floor(d.time_ms / 3600000)).padStart(2, "0")}` +
    `${String(Math.floor(d.time_ms / 60000) % 60).padStart(2, "0")}` +
    `${String(Math.floor(d.time_ms / 1000) % 60).padStart(2, "0")}</span>` +
    `<span class="snr">${d.snr}</span><span class="msg">${esc(d.message)}</span>` +
    (d.entity ? `<span class="dim small">${esc(d.entity)}</span>` : "");
  row.title = "double-click: reply via WSJT-X";
  row.ondblclick = async () => {
    const r = await post("/api/wsjtx/reply", { key: d.key });
    toast(r.ok ? `Replying to ${d.call || "decode"} in WSJT-X` : `Reply failed: ${r.reason}`);
  };
  const list = $("ft8-list");
  list.prepend(row);
  ft8Rows.push(row);
  while (ft8Rows.length > 120) ft8Rows.shift().remove();
  if (d.watched) toast(`⚑ ${d.call} decoded on FT8`, "alert");
});
bus.on("wsjtx_status", (s) => {
  if (s.disabled) { setChip("chip-wsjtx", false, "WSJT-X ○"); return; }
  if (s.listening) {  // bound to UDP but nothing heard yet
    setChip("chip-wsjtx", false, "WSJT-X ◌", true);
    $("wsjtx-dial").textContent = `listening UDP ${s.listening}`;
    return;
  }
  setChip("chip-wsjtx", true, "WSJT-X ●");
  if (s.dial_mhz) {
    $("wsjtx-dial").textContent =
      `dial ${s.dial_mhz.toFixed(3)} MHz  DX: ${s.dx_call || "-"}`;
  }
});

/* ---------------- ADIF import ---------------- */
$("adif-file").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const text = await file.text();
  const r = await fetch("/api/adif", { method: "POST", body: text });
  const res = await r.json();
  toast(`ADIF: ${res.qsos} QSOs → ${res.entities} entities, +${res.slots_added} slots`);
  loadSpots();
});

/* ---------------- gray-line time scrubber ---------------- */
$("time-scrub").addEventListener("input", (e) => {
  const min = parseInt(e.target.value, 10) || 0;
  worldmap.timeOffsetMin = min;
  const lbl = $("scrub-label");
  if (!min) {
    lbl.textContent = "now";
    lbl.classList.remove("scrubbed");
    $("scrub-now").hidden = true;
  } else {
    const d = new Date(Date.now() + min * 60000);
    const sign = min > 0 ? "+" : "−";
    lbl.textContent = `${sign}${Math.abs(min / 60).toFixed(1)}h → ` +
      `${String(d.getUTCHours()).padStart(2, "0")}${String(d.getUTCMinutes()).padStart(2, "0")}z`;
    lbl.classList.add("scrubbed");
    $("scrub-now").hidden = false;
  }
  worldmap.draw();
});
$("scrub-now").onclick = () => {
  $("time-scrub").value = 0;
  $("time-scrub").dispatchEvent(new Event("input"));
};

/* ---------------- map toggle ---------------- */
$("map-toggle").onclick = () => {
  const sec = $("map-section");
  sec.classList.toggle("collapsed");
  $("map-toggle").textContent = sec.classList.contains("collapsed") ? "show" : "hide";
  if (!sec.classList.contains("collapsed")) worldmap.resize();
};

/* ---------------- boot ---------------- */
loadSpots();
fetch("/api/rig").then((r) => r.json()).then((r) => bus.handlers.rig.forEach((f) => f(r)));
