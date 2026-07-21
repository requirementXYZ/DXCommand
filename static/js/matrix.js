"use strict";
/* DXpedition slot matrix (Club Log heritage): your log vs their activity,
   band x mode, with a 24 h activity timeline and click-to-tune. */

const Matrix = {
  call: null,

  init() {
    $("matrix-close").onclick = () => { $("matrix-overlay").hidden = true; };
    $("matrix-overlay").addEventListener("click", (e) => {
      if (e.target.id === "matrix-overlay") $("matrix-overlay").hidden = true;
    });
    $("matrix-watch").onclick = () => {
      if (Matrix.call) addWatch(Matrix.call);
      $("matrix-watch").textContent = "⚑ watching";
    };
  },

  async open(call) {
    const r = await fetch(`/api/matrix?call=${encodeURIComponent(call)}`);
    if (!r.ok) { toast(`Cannot resolve ${call} to a DXCC entity`); return; }
    const m = await r.json();
    Matrix.call = m.call;
    $("matrix-title").textContent = m.call;
    $("matrix-sub").textContent =
      `${m.entity.name} · ${m.entity.cont} · CQ ${m.entity.cqz}`;
    $("matrix-watch").textContent = m.watched ? "⚑ watching" : "⚑ watch";
    Matrix.renderGrid(m);
    Matrix.renderTimeline(m);
    $("matrix-overlay").hidden = false;
  },

  renderGrid(m) {
    const act = {};
    for (const a of m.activity) act[`${a.band}|${a.mode}`] = a;
    const grid = $("matrix-grid");
    grid.style.gridTemplateColumns = `56px repeat(${m.modes.length}, 1fr)`;
    grid.replaceChildren();
    const add = (el) => grid.appendChild(el);
    const head = (text) => {
      const d = document.createElement("div");
      d.className = "mx-head"; d.textContent = text; return d;
    };
    add(head(""));
    m.modes.forEach((mode) => add(head(mode)));
    const now = Date.now() / 1000;
    for (const band of m.bands) {
      const b = document.createElement("div");
      b.className = "mx-head mx-band"; b.textContent = band;
      add(b);
      for (const mode of m.modes) {
        const st = m.status[band][mode];       // "", "W", "C"
        const a = act[`${band}|${mode}`];
        const cell = document.createElement("div");
        cell.className = "mx-cell " + (st ? `st-${st}` : "st-need");
        cell.textContent = st === "C" ? "✓✓" : st === "W" ? "✓" : "·";
        if (a) {
          const age = now - a.last_ts;
          const dot = document.createElement("span");
          dot.className = "dot" + (age > 3600 ? " old" : "");
          cell.appendChild(dot);
          cell.classList.add("active");
          cell.title = `${a.count} spot${a.count > 1 ? "s" : ""} in 24 h · last ` +
            `${fmtAge(Math.floor(age))} ago on ${fmtFreqKhz(a.last_freq)} — click to tune`;
          cell.onclick = () => {
            tuneSpot({ freq: a.last_freq, mode: mode, dx_call: m.call,
                       split_tx_khz: a.split_tx });
            $("matrix-overlay").hidden = true;
          };
        } else {
          cell.title = st === "C" ? "confirmed in your log"
            : st === "W" ? "worked, not confirmed"
            : "needed — not in your log";
        }
        add(cell);
      }
    }
  },

  renderTimeline(m) {
    const wrap = $("matrix-timeline");
    wrap.replaceChildren();
    if (!m.timeline.length) {
      wrap.innerHTML = `<div class="dim small">no spots recorded in the last 24 h</div>`;
      return;
    }
    const nowH = Math.floor(Date.now() / 3600000);   // current hour bucket
    const counts = {};                                // band -> hourIndex -> count
    const bandsSeen = new Set();
    for (const t of m.timeline) {
      const idx = 23 - (nowH - Math.floor(t.hour_ts / 3600));
      if (idx < 0 || idx > 23) continue;
      bandsSeen.add(t.band);
      (counts[t.band] = counts[t.band] || {})[idx] =
        (counts[t.band][idx] || 0) + t.count;
    }
    const bands = m.bands.filter((b) => bandsSeen.has(b));
    for (const band of bands) {
      const row = document.createElement("div");
      row.className = "tl-row";
      const label = document.createElement("span");
      label.className = "tl-band"; label.textContent = band;
      row.appendChild(label);
      for (let i = 0; i < 24; i++) {
        const c = (counts[band] || {})[i] || 0;
        const cell = document.createElement("span");
        cell.className = "tl-cell" + (c ? (c >= 10 ? " a3" : c >= 4 ? " a2" : " a1") : "");
        const hourUtc = new Date((nowH - (23 - i)) * 3600000).getUTCHours();
        if (c) cell.title = `${String(hourUtc).padStart(2, "0")}00z — ${c} spots`;
        row.appendChild(cell);
      }
      wrap.appendChild(row);
    }
    const hours = document.createElement("div");
    hours.className = "tl-hours";
    for (let i = 0; i < 24; i += 4) {
      const h = new Date((nowH - (23 - i)) * 3600000).getUTCHours();
      const s = document.createElement("span");
      s.textContent = `${String(h).padStart(2, "0")}z`;
      hours.appendChild(s);
    }
    wrap.appendChild(hours);
  },
};

Matrix.init();
