"use strict";
/* Gray-line world map (DX Atlas heritage): equirectangular projection,
   live solar terminator, spot markers, great-circle path to selection.
   Every marker is clickable: a popup shows details and one-click tune. */

class WorldMap {
  constructor(canvas, onTune) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.onTune = onTune || (() => {});
    this.land = null;           // GeoJSON features
    this.spots = [];
    this.beacons = [];
    this.home = null;           // {lat, lon, call, grid}
    this.selected = null;       // spot with dxcc
    this.markers = [];          // rebuilt each draw: {x, y, type, data}
    this.popup = this._makePopup();
    this.loadLand();
    canvas.addEventListener("click", (e) => this.click(e));
    canvas.addEventListener("mousemove", (e) => {
      canvas.style.cursor = this.hits(e.offsetX, e.offsetY).length ? "pointer" : "default";
    });
    document.addEventListener("click", (e) => {
      if (!this.popup.contains(e.target) && e.target !== canvas) this.hidePopup();
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") this.dismiss(); });
    new ResizeObserver(() => this.resize()).observe(canvas.parentElement);
    this.resize();
    setInterval(() => this.draw(), 30000); // terminator crawl
  }

  _makePopup() {
    const div = document.createElement("div");
    div.id = "map-popup";
    div.hidden = true;
    document.body.appendChild(div);
    return div;
  }

  async loadLand() {
    try {
      const r = await fetch("/api/worldmap");
      if (r.ok) { this.land = (await r.json()).features; }
      else { $("map-info").textContent = "coastlines unavailable offline - grid only"; }
    } catch { /* offline */ }
    this.draw();
  }

  resize() {
    this.canvas.width = this.canvas.clientWidth;
    this.canvas.height = this.canvas.clientHeight;
    this.draw();
  }

  xy(lat, lon) {
    return [(lon + 180) / 360 * this.canvas.width,
            (90 - lat) / 180 * this.canvas.height];
  }

  /* ---------------- marker interaction ---------------- */
  hits(x, y, radius = 9) {
    return this.markers
      .map((m) => ({ ...m, d: Math.hypot(m.x - x, m.y - y) }))
      .filter((m) => m.d <= radius)
      .sort((a, b) => a.d - b.d);
  }

  click(e) {
    const found = this.hits(e.offsetX, e.offsetY);
    if (!found.length) { this.dismiss(); return; }  // empty map -> clean slate
    e.stopPropagation();
    // Clicking the same marker again toggles everything off.
    const key = found[0].type + ":" + (found[0].data.id || found[0].data.call || "");
    if (!this.popup.hidden && key === this._popupKey) { this.dismiss(); return; }
    this._popupKey = key;
    // Prefer spots; a spot click also selects it (draws the path).
    const spotHits = found.filter((m) => m.type === "spot");
    if (spotHits.length) {
      this.selected = spotHits[0].data;
      this.draw();
    }
    this.showPopup(e.clientX, e.clientY, found);
  }

  /* Close the popup AND clear the selection ring/path: back to just the map. */
  dismiss() {
    this.hidePopup();
    if (this.selected) {
      this.selected = null;
      $("map-info").textContent = "";
      this.draw();
    }
  }

  hidePopup() { this.popup.hidden = true; this._popupKey = null; }

  showPopup(cx, cy, found) {
    const seen = new Set();
    const parts = [];

    const spotRow = (s) => {
      const star = { atno: "★ ATNO", band: "★ new band", mode: "★ new mode" }[s.needed] || "";
      const starCls = s.needed ? ` class="pp-${s.needed}"` : "";
      return `<div class="pp-row pp-tune" data-id="${esc(s.id)}" title="click to tune">
        <b>${esc(s.dx_call)}</b> <span class="pp-freq">${fmtFreqKhz(s.freq)}</span>
        <span class="mchip ${esc(s.mode)}">${esc(s.mode)}</span><span${starCls}>${star}</span>
        <div class="small dim">${esc(s.dxcc ? s.dxcc.name : "?")} · az ${s.dxcc ? s.dxcc.azimuth : "?"}° ·
          ${s.dxcc ? s.dxcc.distance_km : "?"} km · ${fmtAge(Math.floor(Date.now() / 1000 - s.ts))} ago</div>
        ${s.comment ? `<div class="small dim">“${esc(s.comment)}” — de ${esc(s.spotter)}</div>` : ""}
        ${s.split_tx_khz ? `<div class="small pp-split">split: TX ${fmtFreqKhz(s.split_tx_khz)}</div>` : ""}
      </div>`;
    };

    for (const m of found) {
      const key = m.type + ":" + (m.data.id || m.data.call || "");
      if (seen.has(key)) continue;
      seen.add(key);
      if (m.type === "spot") {
        parts.push(spotRow(m.data));
      } else if (m.type === "beacon") {
        const b = m.data;
        parts.push(`<div class="pp-row pp-tune" data-beacon="${esc(String(b.freq))}" title="click to tune (CW)">
          <b>${esc(b.call)}</b> <span class="pp-freq">${fmtFreqKhz(b.freq)}</span>
          <span class="mchip CW">CW</span>
          <div class="small dim">NCDXF beacon · ${esc(b.location)}</div>
          <div class="small dim">on the air right now — ${b.slot_remaining_s}s left in its 10 s slot</div>
        </div>`);
      } else if (m.type === "home") {
        parts.push(`<div class="pp-row"><b>★ ${esc(m.data.call || "Your QTH")}</b>
          <div class="small dim">home station · grid ${esc(m.data.grid || "?")} ·
          ${m.data.lat.toFixed(1)}°, ${m.data.lon.toFixed(1)}°</div>
          <div class="small dim">azimuths and distances are measured from here</div></div>`);
      } else if (m.type === "sun") {
        parts.push(`<div class="pp-row"><b>☀ Sun</b>
          <div class="small dim">subsolar point — local noon directly below</div>
          <div class="small dim">the day/night boundary is the gray line: low-band
          signals along it are often enhanced around your sunrise/sunset</div></div>`);
      }
    }

    this.popup.innerHTML = parts.join("<hr class='pp-sep'>");
    this.popup.hidden = false;
    // clamp to viewport
    const w = 280;
    this.popup.style.left = Math.max(8, Math.min(cx + 12, window.innerWidth - w - 12)) + "px";
    this.popup.style.top = "0px";
    const h = this.popup.getBoundingClientRect().height;
    this.popup.style.top = Math.max(8, Math.min(cy + 12, window.innerHeight - h - 12)) + "px";

    this.popup.querySelectorAll(".pp-tune").forEach((el) => {
      el.addEventListener("click", () => {
        if (el.dataset.beacon) {
          this.onTune({ freq: parseFloat(el.dataset.beacon), mode: "CW" });
        } else {
          const s = this.spots.find((x) => x.id === el.dataset.id);
          if (s) { this.selected = s; this.onTune(s); this.draw(); }
        }
        this.hidePopup();
      });
    });
  }

  /* Subsolar point from current UTC time */
  static subsolar(date) {
    const d = (Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate())
              - Date.UTC(date.getUTCFullYear(), 0, 0)) / 86400000;
    const decl = -23.44 * Math.cos(2 * Math.PI / 365 * (d + 10));
    const utcH = date.getUTCHours() + date.getUTCMinutes() / 60 + date.getUTCSeconds() / 3600;
    const lon = (12 - utcH) * 15;
    return [decl, lon];
  }

  draw() {
    const { ctx, canvas } = this;
    const W = canvas.width, H = canvas.height;
    if (!W || !H) return;
    this.markers = [];
    ctx.fillStyle = "#0d1420";
    ctx.fillRect(0, 0, W, H);

    // graticule
    ctx.strokeStyle = "rgba(38,50,66,.6)";
    for (let lon = -150; lon <= 150; lon += 30) {
      const [x] = this.xy(0, lon);
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    }
    for (let lat = -60; lat <= 60; lat += 30) {
      const [, y] = this.xy(lat, 0);
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }

    // land
    if (this.land) {
      ctx.fillStyle = "#1e2c3d";
      ctx.strokeStyle = "#2c3e54";
      for (const f of this.land) {
        const polys = f.geometry.type === "Polygon"
          ? [f.geometry.coordinates] : f.geometry.coordinates;
        for (const poly of polys) {
          ctx.beginPath();
          for (const ring of poly) {
            ring.forEach(([lon, lat], i) => {
              const [x, y] = this.xy(lat, lon);
              i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
            });
            ctx.closePath();
          }
          ctx.fill(); ctx.stroke();
        }
      }
    }

    this.drawNight();

    // beacons (small diamonds)
    ctx.fillStyle = "#3ddc84";
    for (const b of this.beacons) {
      const [x, y] = this.xy(b.lat, b.lon);
      ctx.beginPath();
      ctx.moveTo(x, y - 3); ctx.lineTo(x + 3, y); ctx.lineTo(x, y + 3); ctx.lineTo(x - 3, y);
      ctx.fill();
      this.markers.push({ x, y, type: "beacon", data: b });
    }

    // spots
    const colors = { CW: "#f0a832", FT8: "#35c0f0", FT4: "#7f7bf5" };
    const now = Date.now() / 1000;
    for (const s of this.spots) {
      if (!s.dxcc) continue;
      const [x, y] = this.xy(s.dxcc.lat, s.dxcc.lon);
      const needCol = { atno: "#ff4d5e", band: "#ff9c3a", mode: "#ffd23a" }[s.needed];
      ctx.globalAlpha = Math.max(0.3, 1 - (now - s.ts) / 1800);
      ctx.fillStyle = needCol || colors[s.mode] || "#5c6c7d";
      ctx.beginPath(); ctx.arc(x, y, s.watched ? 4.5 : 2.8, 0, 7); ctx.fill();
      ctx.globalAlpha = 1;
      this.markers.push({ x, y, type: "spot", data: s });
    }

    // home
    if (this.home) {
      const [x, y] = this.xy(this.home.lat, this.home.lon);
      ctx.fillStyle = "#fff";
      ctx.font = "12px sans-serif";
      ctx.fillText("★", x - 5, y + 4);
      this.markers.push({ x, y, type: "home", data: this.home });
    }

    // great-circle path to selection
    if (this.selected && this.selected.dxcc && this.home) {
      this.drawPath(this.home.lat, this.home.lon,
                    this.selected.dxcc.lat, this.selected.dxcc.lon);
      const [x, y] = this.xy(this.selected.dxcc.lat, this.selected.dxcc.lon);
      ctx.strokeStyle = "#fff";
      ctx.beginPath(); ctx.arc(x, y, 7, 0, 7); ctx.stroke();
      $("map-info").textContent =
        `${this.selected.dx_call} • ${this.selected.dxcc.name} • ` +
        `az ${this.selected.dxcc.azimuth}° • ${this.selected.dxcc.distance_km} km`;
    }

    // sun
    const [slat, slon] = WorldMap.subsolar(new Date());
    const [sx, sy] = this.xy(slat, slon);
    ctx.fillStyle = "#ffd23a";
    ctx.beginPath(); ctx.arc(sx, sy, 5, 0, 7); ctx.fill();
    this.markers.push({ x: sx, y: sy, type: "sun", data: {} });
  }

  drawNight() {
    const { ctx, canvas } = this;
    const [decl, slon] = WorldMap.subsolar(new Date());
    ctx.fillStyle = "rgba(2,6,14,.55)";
    ctx.beginPath();
    const declR = decl * Math.PI / 180;
    let first = true;
    for (let px = 0; px <= canvas.width; px += 4) {
      const lon = px / canvas.width * 360 - 180;
      const hourAngle = (lon - slon) * Math.PI / 180;
      // terminator latitude at this longitude
      const lat = Math.atan(-Math.cos(hourAngle) / Math.tan(declR || 1e-9)) * 180 / Math.PI;
      const [x, y] = this.xy(lat, lon);
      first ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      first = false;
    }
    // close the polygon over the dark pole (north pole dark when decl<0)
    const darkPoleY = decl < 0 ? 0 : canvas.height;
    ctx.lineTo(canvas.width, darkPoleY);
    ctx.lineTo(0, darkPoleY);
    ctx.closePath();
    ctx.fill();
  }

  drawPath(lat1, lon1, lat2, lon2) {
    const { ctx } = this;
    const toR = Math.PI / 180, toD = 180 / Math.PI;
    const p1 = [lat1 * toR, lon1 * toR], p2 = [lat2 * toR, lon2 * toR];
    const d = Math.acos(Math.min(1, Math.sin(p1[0]) * Math.sin(p2[0]) +
      Math.cos(p1[0]) * Math.cos(p2[0]) * Math.cos(p2[1] - p1[1])));
    if (!d) return;
    ctx.strokeStyle = "rgba(61,220,132,.9)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    let prevX = null;
    for (let i = 0; i <= 60; i++) {
      const f = i / 60;
      const A = Math.sin((1 - f) * d) / Math.sin(d);
      const B = Math.sin(f * d) / Math.sin(d);
      const x3 = A * Math.cos(p1[0]) * Math.cos(p1[1]) + B * Math.cos(p2[0]) * Math.cos(p2[1]);
      const y3 = A * Math.cos(p1[0]) * Math.sin(p1[1]) + B * Math.cos(p2[0]) * Math.sin(p2[1]);
      const z3 = A * Math.sin(p1[0]) + B * Math.sin(p2[0]);
      const lat = Math.atan2(z3, Math.hypot(x3, y3)) * toD;
      const lon = Math.atan2(y3, x3) * toD;
      const [x, y] = this.xy(lat, lon);
      if (prevX !== null && Math.abs(x - prevX) > this.canvas.width / 2) {
        ctx.moveTo(x, y); // date-line wrap
      } else if (prevX === null) { ctx.moveTo(x, y); }
      else ctx.lineTo(x, y);
      prevX = x;
    }
    ctx.stroke();
    ctx.lineWidth = 1;
  }
}
