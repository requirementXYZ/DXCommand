"use strict";
/* Quick-start guide overlay + ⓘ info tooltips.
   Tooltips are rendered into a single fixed-position box so they are never
   clipped by scrolling panels. Hover previews; click pins until you click away. */

const Help = {
  KEY: "dxcmd_help_seen",

  open() { $("help-overlay").hidden = false; },

  close() {
    if ($("help-noshow").checked) localStorage.setItem(Help.KEY, "1");
    $("help-overlay").hidden = true;
  },

  init() {
    $("btn-help").onclick = Help.open;
    $("help-close").onclick = Help.close;
    $("help-ok").onclick = Help.close;
    $("help-overlay").addEventListener("click", (e) => {
      if (e.target.id === "help-overlay") Help.close();
    });
    if (!localStorage.getItem(Help.KEY)) {
      Help.open();
      $("help-noshow").checked = true;  // default: show once
    }
  },
};

const InfoTips = {
  pinned: null,

  init() {
    const tip = document.createElement("div");
    tip.id = "tipbox";
    tip.hidden = true;
    document.body.appendChild(tip);

    const show = (el) => {
      tip.textContent = el.dataset.tip;
      tip.hidden = false;
      const r = el.getBoundingClientRect();
      const w = Math.min(300, window.innerWidth - 20);
      tip.style.maxWidth = w + "px";
      tip.style.left = Math.max(8, Math.min(r.left - 8, window.innerWidth - w - 12)) + "px";
      // Prefer below the icon; flip above if it would leave the viewport.
      tip.style.top = (r.bottom + 8) + "px";
      requestAnimationFrame(() => {
        const tr = tip.getBoundingClientRect();
        if (tr.bottom > window.innerHeight - 8) {
          tip.style.top = Math.max(8, r.top - tr.height - 8) + "px";
        }
      });
    };
    const hide = () => { tip.hidden = true; InfoTips.pinned = null; };

    document.querySelectorAll(".info").forEach((el) => {
      el.setAttribute("role", "button");
      el.setAttribute("tabindex", "0");
      el.addEventListener("mouseenter", () => { if (!InfoTips.pinned) show(el); });
      el.addEventListener("mouseleave", () => { if (!InfoTips.pinned) tip.hidden = true; });
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        if (InfoTips.pinned === el) { hide(); return; }
        InfoTips.pinned = el;
        show(el);
      });
    });
    document.addEventListener("click", hide);
    window.addEventListener("resize", hide);
  },
};

Help.init();
InfoTips.init();
