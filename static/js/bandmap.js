"use strict";
/* Vertical band map (Band Master heritage): spots on a frequency ladder,
   CW/FT8 segments shaded, rig cursor, click to QSY. */

const BAND_EDGES = {
  "160m": [1800, 2000], "80m": [3500, 3800], "60m": [5330, 5410],
  "40m": [7000, 7200], "30m": [10100, 10150], "20m": [14000, 14350],
  "17m": [18068, 18168], "15m": [21000, 21450], "12m": [24890, 24990],
  "10m": [28000, 28600], "6m": [50000, 50500],
};
const CW_SEG = { "160m": [1800, 1840], "80m": [3500, 3570], "40m": [7000, 7040],
  "30m": [10100, 10130], "20m": [14000, 14070], "17m": [18068, 18095],
  "15m": [21000, 21070], "12m": [24890, 24915], "10m": [28000, 28070],
  "6m": [50000, 50100] };
const FT_SEG = { "160m": [1840, 1846], "80m": [3573, 3579], "40m": [7074, 7080],
  "30m": [10136, 10143], "20m": [14074, 14083], "17m": [18100, 18107],
  "15m": [21074, 21083], "12m": [24915, 24922], "10m": [28074, 28083],
  "6m": [50313, 50326] };

class BandMap {
  constructor(canvas, onTune) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.band = "20m";
    this.spots = [];
    this.rigKhz = 14025;
    this.onTune = onTune;
    this.hover = null;
    canvas.addEventListener("click", (e) => this.click(e));
    canvas.addEventListener("mousemove", (e) => { this.hover = e.offsetY; this.draw(); });
    canvas.addEventListener("mouseleave", () => { this.hover = null; this.draw(); });
    new ResizeObserver(() => this.resize()).observe(canvas.parentElement);
    this.resize();
  }

  resize() {
    const r = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = r.width;
    this.canvas.height = Math.max(r.height - 26, 100);
    this.draw();
  }

  setBand(b) { this.band = b; $("bandmap-title").textContent = b; this.draw(); }
  setSpots(spots) { this.spots = spots; this.draw(); }
  setRig(khz) {
    this.rigKhz = khz;
    const b = Object.entries(BAND_EDGES).find(([, [lo, hi]]) => khz >= lo && khz <= hi);
    if (b && b[0] !== this.band) this.setBand(b[0]);
    this.draw();
  }

  yFor(khz) {
    const [lo, hi] = BAND_EDGES[this.band];
    return 8 + (1 - (khz - lo) / (hi - lo)) * (this.canvas.height - 16);
  }
  khzFor(y) {
    const [lo, hi] = BAND_EDGES[this.band];
    return hi - ((y - 8) / (this.canvas.height - 16)) * (hi - lo);
  }

  click(e) {
    const spot = this.spotAt(e.offsetY);
    if (spot) this.onTune(spot);
    else this.onTune({ freq: Math.round(this.khzFor(e.offsetY) * 10) / 10 });
  }

  spotAt(y) {
    let best = null, bestD = 7;
    for (const s of this.spots) {
      if (s.band !== this.band) continue;
      const d = Math.abs(this.yFor(s.freq) - y);
      if (d < bestD) { bestD = d; best = s; }
    }
    return best;
  }

  draw() {
    const { ctx, canvas } = this;
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    const [lo, hi] = BAND_EDGES[this.band];

    const seg = (range, color) => {
      if (!range) return;
      const y1 = this.yFor(Math.min(range[1], hi)), y2 = this.yFor(Math.max(range[0], lo));
      ctx.fillStyle = color;
      ctx.fillRect(0, y1, W, y2 - y1);
    };
    seg(CW_SEG[this.band], "rgba(240,168,50,.07)");
    seg(FT_SEG[this.band], "rgba(53,192,240,.09)");

    // frequency ticks
    ctx.font = "9px Consolas, monospace";
    const span = hi - lo;
    const step = span > 300 ? 50 : span > 120 ? 25 : 10;
    for (let f = Math.ceil(lo / step) * step; f <= hi; f += step) {
      const y = this.yFor(f);
      ctx.strokeStyle = "#263242";
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
      ctx.fillStyle = "#7a8a9c";
      ctx.fillText(f.toFixed(0), 3, y - 2);
    }

    // spots
    const now = Date.now() / 1000;
    const colors = { CW: "#f0a832", FT8: "#35c0f0", FT4: "#7f7bf5" };
    for (const s of this.spots) {
      if (s.band !== this.band) continue;
      const y = this.yFor(s.freq);
      const age = now - s.ts;
      const alpha = Math.max(0.25, 1 - age / 1800);
      const needCol = { atno: "#ff4d5e", band: "#ff9c3a", mode: "#ffd23a" }[s.needed];
      ctx.globalAlpha = alpha;
      ctx.fillStyle = needCol || colors[s.mode] || "#5c6c7d";
      ctx.beginPath(); ctx.arc(30, y, s.watched ? 4 : 3, 0, 7); ctx.fill();
      ctx.font = (s.needed === "atno" || s.watched ? "bold " : "") + "11px Consolas, monospace";
      ctx.fillText(s.dx_call, 38, y + 3.5);
      ctx.globalAlpha = 1;
    }

    // rig cursor
    if (this.rigKhz >= lo && this.rigKhz <= hi) {
      const y = this.yFor(this.rigKhz);
      ctx.strokeStyle = "#3ddc84"; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
      ctx.fillStyle = "#3ddc84";
      ctx.beginPath(); ctx.moveTo(0, y - 5); ctx.lineTo(8, y); ctx.lineTo(0, y + 5); ctx.fill();
      ctx.lineWidth = 1;
    }

    // hover crosshair
    if (this.hover !== null) {
      const s = this.spotAt(this.hover);
      ctx.fillStyle = "#d5dee8"; ctx.font = "10px Consolas, monospace";
      const label = s ? `${s.dx_call} ${fmtFreqKhz(s.freq)}` : fmtFreqKhz(this.khzFor(this.hover));
      ctx.fillText(label, 4, Math.max(12, this.hover - 6));
    }
  }
}
