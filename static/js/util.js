"use strict";
/* Shared helpers + websocket client */

const $ = (id) => document.getElementById(id);

/* Escape untrusted text (cluster comments, FT8 messages) before innerHTML */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function fmtFreqKhz(khz) {
  return khz.toFixed(1);   // cluster style: 14012.7
}

function fmtAge(s) {
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return `${Math.floor(s / 3600)}h${Math.floor((s % 3600) / 60)}m`;
}

function utcHHMM(ts) {
  const d = new Date(ts * 1000);
  return d.getUTCHours().toString().padStart(2, "0") +
         d.getUTCMinutes().toString().padStart(2, "0");
}

function toast(text, cls = "") {
  const t = document.createElement("div");
  t.className = "toast " + cls;
  t.textContent = text;
  $("toasts").appendChild(t);
  setTimeout(() => t.remove(), 4200);
}

async function post(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return r.json();
}

/* Auto-reconnecting websocket dispatching frames to registered handlers */
class Bus {
  constructor() { this.handlers = {}; this.connect(); }
  on(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); }
  connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}/ws`);
    this.ws.onmessage = (ev) => {
      const { type, data } = JSON.parse(ev.data);
      (this.handlers[type] || []).forEach((fn) => fn(data));
    };
    this.ws.onclose = () => setTimeout(() => this.connect(), 2000);
  }
}
