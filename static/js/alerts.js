"use strict";
/* Alerts panel: rule checkboxes (persisted server-side via /api/config),
   desktop notifications, Web-Audio sounds, and a reviewable alert log. */

const Alerts = {
  cfg: null,
  desktop: localStorage.getItem("dxcmd_alert_desktop") === "1",

  init() {
    const ids = ["alerts-enabled", "alert-atno", "alert-band", "alert-mode",
                 "alert-watch", "alert-mycont"];
    ids.forEach((id) => { $(id).addEventListener("change", () => Alerts.save()); });
    $("alert-quiet").addEventListener("change", () => Alerts.save());
    $("alert-sound").addEventListener("change", () => Alerts.save());
    $("alert-test").onclick = () => Alerts.beep($("alert-sound").value || "ping");
    $("alert-desktop").checked = Alerts.desktop;
    $("alert-desktop").addEventListener("change", async (e) => {
      Alerts.desktop = e.target.checked;
      localStorage.setItem("dxcmd_alert_desktop", Alerts.desktop ? "1" : "0");
      if (Alerts.desktop && "Notification" in window &&
          Notification.permission === "default") {
        const perm = await Notification.requestPermission();
        if (perm !== "granted") toast("Desktop notifications blocked by the browser");
      }
    });
    fetch("/api/alerts").then((r) => r.json())
      .then((log) => log.slice(0, 30).reverse().forEach((a) => Alerts.addLogRow(a, false)));
  },

  applyConfig(a) {           // from app_info frame
    if (!a) return;
    this.cfg = a;
    $("alerts-enabled").checked = !!a.enabled;
    $("alert-atno").checked = !!a.notify_atno;
    $("alert-band").checked = !!a.notify_band;
    $("alert-mode").checked = !!a.notify_mode;
    $("alert-watch").checked = !!a.notify_watch;
    $("alert-mycont").checked = !!a.only_my_continent;
    $("alert-quiet").value = a.quiet || "";
    $("alert-sound").value = a.sound || "ping";
  },

  async save() {
    const body = { alerts: {
      enabled: $("alerts-enabled").checked,
      notify_atno: $("alert-atno").checked,
      notify_band: $("alert-band").checked,
      notify_mode: $("alert-mode").checked,
      notify_watch: $("alert-watch").checked,
      only_my_continent: $("alert-mycont").checked,
      quiet: $("alert-quiet").value.trim(),
      sound: $("alert-sound").value,
    } };
    await post("/api/config", body);
    toast("Alert settings saved");
  },

  onAlert(a) {
    this.addLogRow(a, true);
    toast(`🔔 ${a.text}`, "alert");
    if (a.sound && a.sound !== "off") this.beep(a.sound);
    if (this.desktop && "Notification" in window &&
        Notification.permission === "granted" && !document.hasFocus()) {
      new Notification("DX Command", { body: a.text });
    }
  },

  addLogRow(a, prepend) {
    const row = document.createElement("div");
    row.className = `alert-row r-${a.reason}`;
    const d = new Date(a.ts * 1000);
    const hm = `${String(d.getUTCHours()).padStart(2, "0")}${String(d.getUTCMinutes()).padStart(2, "0")}z`;
    row.innerHTML = `<span class="when">${hm}</span><span>${esc(a.text)}</span>`;
    if (a.freq) {
      row.title = "click to tune";
      row.onclick = () => tuneSpot({ freq: a.freq, mode: a.mode,
                                     dx_call: a.call, split_tx_khz: a.split_tx_khz });
    }
    const log = $("alert-log");
    prepend ? log.prepend(row) : log.append(row);
    while (log.children.length > 60) log.lastChild.remove();
    $("alert-count").textContent = log.children.length ? `${log.children.length} logged` : "";
  },

  beep(kind) {
    const actx = new (window.AudioContext || window.webkitAudioContext)();
    const note = (freq, t0, dur, gain = 0.25) => {
      const o = actx.createOscillator();
      const g = actx.createGain();
      o.frequency.value = freq;
      o.connect(g).connect(actx.destination);
      g.gain.setValueAtTime(0, t0);
      g.gain.linearRampToValueAtTime(gain, t0 + 0.01);
      g.gain.setValueAtTime(gain, t0 + dur - 0.03);
      g.gain.linearRampToValueAtTime(0, t0 + dur);
      o.start(t0); o.stop(t0 + dur + 0.05);
    };
    const t = actx.currentTime + 0.02;
    if (kind === "alarm") {
      [700, 950, 700, 950].forEach((f, i) => note(f, t + i * 0.18, 0.16, 0.3));
    } else {
      note(880, t, 0.12); note(1320, t + 0.15, 0.18);
    }
    setTimeout(() => actx.close(), 1500);
  },
};

Alerts.init();
