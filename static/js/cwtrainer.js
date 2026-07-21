"use strict";
/* CW Pileup Trainer (Morse Runner heritage), fully in-browser via Web Audio.

   Full QSO flow ("call + serial" mode):
     pileup calls -> you copy a call and type it -> your station answers
     "<CALL> 5NN" -> they come back "R 5NN <serial>" -> you type the serial ->
     "TU" and the next callers appear. Misses replay; "?" asks for a repeat.
   Realism options: QSB (per-station fading), QRN (band noise + static
   crashes), QRM (an interfering station over the pileup). "auto (ramp)"
   grows pileup depth as your QSO count climbs. Sessions are scored and a
   local high-score table is kept. */

const MORSE = {
  A: ".-", B: "-...", C: "-.-.", D: "-..", E: ".", F: "..-.", G: "--.", H: "....",
  I: "..", J: ".---", K: "-.-", L: ".-..", M: "--", N: "-.", O: "---", P: ".--.",
  Q: "--.-", R: ".-.", S: "...", T: "-", U: "..-", V: "...-", W: ".--", X: "-..-",
  Y: "-.--", Z: "--..", 0: "-----", 1: ".----", 2: "..---", 3: "...--", 4: "....-",
  5: ".....", 6: "-....", 7: "--...", 8: "---..", 9: "----.", "/": "-..-.",
  "?": "..--..",
};

const PREFIXES = ["K", "W", "N", "VE", "JA", "G", "DL", "F", "EA", "I", "SM",
  "OH", "OK", "SP", "UA", "PY", "LU", "VK", "ZL", "ZS", "HB9", "OE", "ON",
  "PA", "OZ", "LA", "9A", "S5", "YO", "LZ", "UR", "HA", "EI", "CT", "5Z4",
  "JW", "TF", "VP8", "FK", "9M2", "HL", "BV", "4X", "TA", "XE", "CE", "HK"];

function randomCall() {
  const p = PREFIXES[Math.floor(Math.random() * PREFIXES.length)];
  const digit = /\d$/.test(p) ? "" : Math.floor(Math.random() * 10);
  const len = 1 + Math.floor(Math.random() * 2 + Math.random());
  let suffix = "";
  for (let i = 0; i < Math.min(len, 3); i++)
    suffix += String.fromCharCode(65 + Math.floor(Math.random() * 26));
  return p + digit + suffix;
}

class CwStation {
  constructor(actx, call, wpm, pitch, gain, qsb) {
    this.actx = actx; this.call = call; this.wpm = wpm;
    this.pitch = pitch; this.gain = gain; this.qsb = qsb;
    this.serial = String(1 + Math.floor(Math.random() * 999));
  }

  /* Schedule morse text starting at t; returns end time. */
  play(t, text = this.call) {
    const dit = 1.2 / this.wpm;
    const osc = this.actx.createOscillator();
    const key = this.actx.createGain();          // keying envelope
    const fade = this.actx.createGain();         // QSB
    osc.frequency.value = this.pitch;
    key.gain.value = 0;
    fade.gain.value = 1;
    osc.connect(key).connect(fade).connect(this.actx.destination);
    if (this.qsb) {
      const lfo = this.actx.createOscillator();
      const depth = this.actx.createGain();
      lfo.frequency.value = 0.12 + Math.random() * 0.3;
      depth.gain.value = 0.42;                   // fade between ~0.16 and 1.0
      fade.gain.value = 0.58;
      lfo.connect(depth).connect(fade.gain);
      lfo.start(t);
      this._lfo = lfo;
    }
    osc.start(t);
    const ramp = 0.004;
    for (const ch of text) {
      const code = MORSE[ch];
      if (!code) { t += 3 * dit; continue; }
      for (const sym of code) {
        const dur = sym === "." ? dit : 3 * dit;
        key.gain.setValueAtTime(0, t);
        key.gain.linearRampToValueAtTime(this.gain, t + ramp);
        key.gain.setValueAtTime(this.gain, t + dur - ramp);
        key.gain.linearRampToValueAtTime(0, t + dur);
        t += dur + dit;
      }
      t += 2 * dit; // inter-character (3 dits total)
    }
    osc.stop(t + 0.1);
    if (this._lfo) this._lfo.stop(t + 0.1);
    return t;
  }
}

/* Band-noise engine for QRN: soft background hiss + random static crashes. */
class Qrn {
  constructor(actx) {
    this.actx = actx;
    this.timer = null;
    const len = actx.sampleRate * 2;
    const buf = actx.createBuffer(1, len, actx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    this.buffer = buf;
  }
  start() {
    this.src = this.actx.createBufferSource();
    this.src.buffer = this.buffer; this.src.loop = true;
    const bp = this.actx.createBiquadFilter();
    bp.type = "bandpass"; bp.frequency.value = 700; bp.Q.value = 0.4;
    this.bg = this.actx.createGain();
    this.bg.gain.value = 0.035;
    this.src.connect(bp).connect(this.bg).connect(this.actx.destination);
    this.src.start();
    this.crash();
  }
  crash() {
    this.timer = setTimeout(() => {
      const t = this.actx.currentTime;
      const src = this.actx.createBufferSource();
      src.buffer = this.buffer;
      src.playbackRate.value = 0.6 + Math.random();
      const g = this.actx.createGain();
      const dur = 0.03 + Math.random() * 0.12;
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.15 + Math.random() * 0.3, t + 0.005);
      g.gain.exponentialRampToValueAtTime(0.001, t + dur);
      src.connect(g).connect(this.actx.destination);
      src.start(t); src.stop(t + dur + 0.05);
      this.crash();
    }, 400 + Math.random() * 2600);
  }
  stop() {
    clearTimeout(this.timer);
    if (this.src) { try { this.src.stop(); } catch { /* already stopped */ } }
  }
}

const HIST_KEY = "dxcmd_cw_history";

class CwTrainer {
  constructor() {
    this.actx = null;
    this.active = [];         // stations currently calling
    this.running = false;
    this.phase = "call";      // "call" | "exch"
    this.target = null;       // station we're working in exch phase
    this.qrn = null;
    this.recallTimer = null;
    this.score = this.freshScore();
    $("btn-cw-trainer").onclick = () => { $("cw-overlay").hidden = false; this.renderBest(); };
    $("cw-close").onclick = () => { this.stopRun(); $("cw-overlay").hidden = true; };
    $("cw-start").onclick = () => this.running ? this.stopRun() : this.startRun();
    $("cw-repeat").onclick = () => this.repeat();
    $("cw-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this.check();
    });
    this.renderBest();
  }

  freshScore() {
    return { qsos: 0, ok: 0, bad: 0, exchErr: 0, streak: 0, bestStreak: 0,
             started: 0 };
  }

  get exchMode() { return $("cw-mode").value === "exch"; }

  depth() {
    const sel = parseInt($("cw-stations").value, 10);
    if (sel > 0) return sel;
    return Math.min(1 + Math.floor(this.score.qsos / 3), 5);   // ramp
  }

  startRun() {
    if (!this.actx) this.actx = new (window.AudioContext || window.webkitAudioContext)();
    this.actx.resume();
    this.running = true;
    this.score = this.freshScore();
    this.score.started = Date.now();
    this.updateScore();
    $("cw-start").textContent = "■ STOP";
    $("cw-input").disabled = false;
    $("cw-repeat").disabled = false;
    $("cw-input").focus();
    if ($("cw-qrn").checked) { this.qrn = new Qrn(this.actx); this.qrn.start(); }
    this.newPileup();
  }

  stopRun() {
    if (!this.running) return;
    this.running = false;
    clearTimeout(this.recallTimer);
    if (this.qrn) { this.qrn.stop(); this.qrn = null; }
    $("cw-start").textContent = "▶ START";
    $("cw-input").disabled = true;
    $("cw-repeat").disabled = true;
    this.setPhase("call");
    this.active = [];
    this.target = null;
    this.recordSession();
  }

  setPhase(phase) {
    this.phase = phase;
    const inp = $("cw-input");
    inp.classList.toggle("exch-phase", phase === "exch");
    inp.placeholder = phase === "exch"
      ? "copy the serial (5NN ###) + Enter — '?' for a repeat"
      : "type the callsign you hear + Enter";
  }

  newPileup() {
    if (!this.running) return;
    this.setPhase("call");
    this.target = null;
    const n = this.depth();
    $("cw-depth").textContent = `pileup: ${n}`;
    const baseWpm = parseInt($("cw-speed").value, 10);
    const qsb = $("cw-qsb").checked;
    this.active = [];
    const used = new Set();
    for (let i = 0; i < n; i++) {
      let call;
      do { call = randomCall(); } while (used.has(call));
      used.add(call);
      this.active.push(new CwStation(
        this.actx, call,
        baseWpm + Math.floor(Math.random() * 5),
        420 + Math.random() * 480,
        0.12 + Math.random() * 0.25,
        qsb));
    }
    this.playPileup(0.25);
  }

  playPileup(delay) {
    if (!this.actx || !this.running) return;
    const t0 = this.actx.currentTime + delay;
    let end = t0;
    for (const st of this.active) end = Math.max(end, st.play(t0 + Math.random() * 0.9));
    if ($("cw-qrm").checked && Math.random() < 0.4) this.playQrm(t0);
    this.armRecall(end);
  }

  playQrm(t0) {
    const texts = ["TEST", "CQ CQ", "QRL?", "VVV", randomCall()];
    const st = new CwStation(this.actx, "QRM",
      22 + Math.floor(Math.random() * 10),
      380 + Math.random() * 620, 0.1 + Math.random() * 0.1, false);
    st.play(t0 + Math.random() * 0.6, texts[Math.floor(Math.random() * texts.length)]);
  }

  /* If the operator goes quiet, the pileup (or the worked station) tries again. */
  armRecall(audioEndTime) {
    clearTimeout(this.recallTimer);
    const waitMs = (audioEndTime - this.actx.currentTime) * 1000 + 6000;
    this.recallTimer = setTimeout(() => {
      if (!this.running) return;
      this.phase === "exch" ? this.sendExchange(0.1) : this.playPileup(0.1);
    }, waitMs);
  }

  /* Our own station: fixed pitch/speed so "you" always sound like you. */
  mySend(text, delay = 0.15) {
    const me = new CwStation(this.actx, "ME", 30, 650, 0.3, false);
    return me.play(this.actx.currentTime + delay, text);
  }

  sendExchange(delay = 0.2) {
    // Target answers: "R 5NN <serial>"
    const end = this.target.play(this.actx.currentTime + delay,
                                 `R 5NN ${this.target.serial}`);
    this.armRecall(end);
  }

  repeat() {
    if (this.phase === "exch" && this.target) this.sendExchange(0.15);
    else this.playPileup(0.15);
  }

  log(text, cls) {
    const div = document.createElement("div");
    div.className = cls || "";
    div.textContent = text;
    $("cw-log").prepend(div);
    while ($("cw-log").children.length > 80) $("cw-log").lastChild.remove();
  }

  check() {
    const typed = $("cw-input").value.trim().toUpperCase();
    $("cw-input").value = "";
    if (!this.running) return;
    if (this.phase === "exch") return this.checkExchange(typed);
    if (!typed) { this.playPileup(0.2); return; }
    const idx = this.active.findIndex((s) => s.call === typed);
    if (idx >= 0) {
      this.score.ok++;
      this.target = this.active[idx];
      if (this.exchMode) {
        this.setPhase("exch");
        // You: "<CALL> 5NN", then they come back with the serial.
        const myEnd = this.mySend(`${this.target.call} 5NN`);
        const end = this.target.play(myEnd + 0.4, `R 5NN ${this.target.serial}`);
        this.armRecall(end);
        this.log(`→ ${typed} 5NN … copy the serial`, "");
      } else {
        this.active.splice(idx, 1);
        this.completeQso();
      }
    } else {
      this.score.bad++;
      this.score.streak = 0;
      const calls = this.active.map((s) => s.call).join("  ");
      this.log(`✗ ${typed}  (calling: ${calls})`, "bad");
      this.playPileup(0.3);
    }
    this.updateScore();
  }

  checkExchange(typed) {
    const norm = (s) => s.replace(/^0+/, "") || "0";
    const cleaned = typed.replace(/^5NN\s*/, "").replace(/\s/g, "");
    if (!typed || typed === "?") { this.sendExchange(0.15); return; }
    if (norm(cleaned) === norm(this.target.serial)) {
      const i = this.active.indexOf(this.target);
      if (i >= 0) this.active.splice(i, 1);
      this.log(`✓ ${this.target.call} 5NN ${this.target.serial}`, "ok");
      this.completeQso();
    } else {
      this.score.exchErr++;
      this.score.streak = 0;
      this.log(`✗ nr ${typed} (sent ${this.target.serial}) — listen again`, "bad");
      this.sendExchange(0.3);
    }
    this.updateScore();
  }

  completeQso() {
    this.score.qsos++;
    this.score.streak++;
    this.score.bestStreak = Math.max(this.score.bestStreak, this.score.streak);
    if (!this.exchMode) this.log(`✓ ${this.target ? this.target.call : ""}`, "ok");
    this.target = null;
    this.setPhase("call");
    const end = this.mySend("TU");
    const wait = Math.max(0, (end - this.actx.currentTime) * 1000 + 250);
    setTimeout(() => {
      if (!this.running) return;
      if (this.active.length === 0) this.newPileup();
      else {
        $("cw-depth").textContent = `pileup: ${this.active.length}`;
        this.playPileup(0.1);
      }
    }, wait);
    this.updateScore();
  }

  updateScore() {
    $("cw-qsos").textContent = this.score.qsos;
    $("cw-ok").textContent = this.score.ok;
    $("cw-bad").textContent = this.score.bad;
    $("cw-exch-err").textContent = this.score.exchErr;
    $("cw-streak").textContent = this.score.streak;
  }

  /* ---------------- session history / high scores ---------------- */
  history() {
    try { return JSON.parse(localStorage.getItem(HIST_KEY)) || []; }
    catch { return []; }
  }

  recordSession() {
    const s = this.score;
    if (!s.started || (s.qsos === 0 && s.ok === 0 && s.bad === 0)) return;
    const hist = this.history();
    hist.push({
      ts: Date.now(),
      qsos: s.qsos,
      missed: s.bad,
      exchErr: s.exchErr,
      bestStreak: s.bestStreak,
      minutes: Math.max(1, Math.round((Date.now() - s.started) / 60000)),
      mode: this.exchMode ? "call+serial" : "calls",
      opts: ["qsb", "qrn", "qrm"].filter((o) => $(`cw-${o}`).checked).join("+") || "clean",
    });
    while (hist.length > 20) hist.shift();
    localStorage.setItem(HIST_KEY, JSON.stringify(hist));
    this.log(`— session: ${s.qsos} QSOs, best streak ${s.bestStreak} —`, "");
    this.renderBest(Date.now());
  }

  renderBest(latestTs) {
    const hist = this.history();
    const wrap = $("cw-best");
    if (!hist.length) { wrap.innerHTML = ""; return; }
    const best = [...hist].sort((a, b) => b.qsos - a.qsos).slice(0, 5);
    const rows = best.map((h) => {
      const d = new Date(h.ts);
      const when = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      const acc = h.qsos + h.missed > 0
        ? Math.round(100 * h.qsos / (h.qsos + h.missed)) : 100;
      return `<tr${h.ts === latestTs ? ' class="latest"' : ""}><td>${when}</td>` +
        `<td>${h.qsos} QSO</td><td>${acc}%</td><td>str ${h.bestStreak}</td>` +
        `<td>${h.mode}</td><td>${h.opts}</td></tr>`;
    }).join("");
    wrap.innerHTML = `<table><tr><th>BEST SESSIONS</th><th>QSOs</th>` +
      `<th>acc</th><th>streak</th><th>mode</th><th>cond</th></tr>${rows}</table>`;
  }
}
