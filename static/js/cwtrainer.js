"use strict";
/* CW Pileup Trainer (Morse Runner heritage), fully in-browser via Web Audio.
   N stations call you simultaneously with random pitch/speed/level;
   copy a call, type it, work them one by one. */

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
  constructor(actx, call, wpm, pitch, gain) {
    this.actx = actx; this.call = call; this.wpm = wpm;
    this.pitch = pitch; this.gain = gain;
  }
  /* schedule the callsign starting at t (seconds, AudioContext time) */
  play(t) {
    const dit = 1.2 / this.wpm;
    const osc = this.actx.createOscillator();
    const g = this.actx.createGain();
    osc.frequency.value = this.pitch;
    g.gain.value = 0;
    osc.connect(g).connect(this.actx.destination);
    osc.start(t);
    const ramp = 0.004;
    for (const ch of this.call) {
      const code = MORSE[ch];
      if (!code) { t += 3 * dit; continue; }
      for (const sym of code) {
        const dur = sym === "." ? dit : 3 * dit;
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(this.gain, t + ramp);
        g.gain.setValueAtTime(this.gain, t + dur - ramp);
        g.gain.linearRampToValueAtTime(0, t + dur);
        t += dur + dit;
      }
      t += 2 * dit; // inter-character (3 dits total)
    }
    osc.stop(t + 0.1);
    return t;
  }
}

class CwTrainer {
  constructor() {
    this.actx = null;
    this.active = [];      // stations currently calling
    this.running = false;
    this.score = { ok: 0, bad: 0, streak: 0 };
    $("btn-cw-trainer").onclick = () => { $("cw-overlay").hidden = false; };
    $("cw-close").onclick = () => { this.stopRun(); $("cw-overlay").hidden = true; };
    $("cw-start").onclick = () => this.running ? this.stopRun() : this.startRun();
    $("cw-repeat").onclick = () => this.playPileup(0.15);
    $("cw-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this.check();
    });
  }

  startRun() {
    if (!this.actx) this.actx = new (window.AudioContext || window.webkitAudioContext)();
    this.actx.resume();
    this.running = true;
    $("cw-start").textContent = "■ STOP";
    $("cw-input").disabled = false;
    $("cw-repeat").disabled = false;
    $("cw-input").focus();
    this.newPileup();
  }

  stopRun() {
    this.running = false;
    $("cw-start").textContent = "▶ START";
    $("cw-input").disabled = true;
    $("cw-repeat").disabled = true;
    this.active = [];
  }

  newPileup() {
    if (!this.running) return;
    const n = parseInt($("cw-stations").value, 10);
    const baseWpm = parseInt($("cw-speed").value, 10);
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
        0.12 + Math.random() * 0.25));
    }
    this.playPileup(0.25);
  }

  playPileup(delay) {
    if (!this.actx) return;
    const t0 = this.actx.currentTime + delay;
    for (const st of this.active) st.play(t0 + Math.random() * 0.9);
  }

  sendExchange(cb) {
    // "TU" from you at fixed pitch, then callback
    const st = new CwStation(this.actx, "TU", 30, 650, 0.3);
    const end = st.play(this.actx.currentTime + 0.15);
    setTimeout(cb, Math.max(0, (end - this.actx.currentTime) * 1000 + 250));
  }

  log(text, cls) {
    const div = document.createElement("div");
    div.className = cls || "";
    div.textContent = text;
    $("cw-log").prepend(div);
  }

  check() {
    const typed = $("cw-input").value.trim().toUpperCase();
    $("cw-input").value = "";
    if (!typed || !this.running) return;
    const idx = this.active.findIndex((s) => s.call === typed);
    if (idx >= 0) {
      this.score.ok++; this.score.streak++;
      this.log(`✓ ${typed}`, "ok");
      this.active.splice(idx, 1);
      this.sendExchange(() => {
        if (!this.running) return;
        if (this.active.length === 0) this.newPileup();
        else this.playPileup(0.1);
      });
    } else {
      this.score.bad++; this.score.streak = 0;
      const calls = this.active.map((s) => s.call).join("  ");
      this.log(`✗ ${typed}  (calling: ${calls})`, "bad");
      this.playPileup(0.3);
    }
    $("cw-ok").textContent = this.score.ok;
    $("cw-bad").textContent = this.score.bad;
    $("cw-streak").textContent = this.score.streak;
  }
}
