"use strict";
/* DXCC worked-by-band table (award-chart view): entities down the side,
   bands across, ✓ worked / ✓✓ confirmed cells with per-mode tooltips.
   Data comes from /api/worked (the same tracker that drives needed-flags). */

const DxccTable = {
  data: null,
  mode: "ALL",
  search: "",

  init() {
    $("btn-dxcc").onclick = () => DxccTable.open();
    $("dxcc-close").onclick = () => { $("dxcc-overlay").hidden = true; };
    $("dxcc-overlay").addEventListener("click", (e) => {
      if (e.target.id === "dxcc-overlay") $("dxcc-overlay").hidden = true;
    });
    document.querySelectorAll("#dxcc-modes .fbtn").forEach((btn) => {
      btn.onclick = () => {
        DxccTable.mode = btn.dataset.mode;
        document.querySelectorAll("#dxcc-modes .fbtn").forEach((b) =>
          b.classList.toggle("active", b === btn));
        DxccTable.render();
      };
    });
    $("dxcc-search").addEventListener("input", (e) => {
      DxccTable.search = e.target.value.toUpperCase();
      DxccTable.render();
    });
  },

  async open() {
    this.data = await (await fetch("/api/worked")).json();
    this.render();
    $("dxcc-overlay").hidden = false;
    $("dxcc-search").focus();
  },

  /* Aggregate one entity+band across the selected mode(s):
     "" = not worked, "W" = worked, "C" = confirmed. */
  cellStatus(bandModes) {
    if (!bandModes) return "";
    const entries = Object.entries(bandModes)
      .filter(([m]) => this.mode === "ALL" || m === this.mode);
    if (!entries.length) return "";
    return entries.some(([, st]) => st === "C") ? "C" : "W";
  },

  render() {
    const d = this.data;
    if (!d) return;
    const bands = d.bands;
    const names = Object.keys(d.entities).sort();
    const shown = names.filter((n) => !this.search || n.toUpperCase().includes(this.search));

    const bandTotals = Object.fromEntries(bands.map((b) => [b, 0]));
    let slotTotal = 0, confTotal = 0;
    const rows = [];
    for (const name of shown) {
      const ent = d.entities[name];
      let entBands = 0;
      const cells = bands.map((b) => {
        const st = this.cellStatus(ent[b]);
        if (st) { entBands++; bandTotals[b]++; slotTotal++; if (st === "C") confTotal++; }
        const modes = ent[b]
          ? Object.entries(ent[b])
              .filter(([m]) => this.mode === "ALL" || m === this.mode)
              .map(([m, s]) => `${m} ${s === "C" ? "✓✓" : "✓"}`).join(", ")
          : "";
        const mark = st === "C" ? "✓✓" : st === "W" ? "✓" : "";
        return `<td class="dx-cell ${st ? "dx-" + st : ""}"` +
               (modes ? ` title="${esc(name)} ${b}: ${esc(modes)}"` : "") + `>${mark}</td>`;
      });
      if (this.mode !== "ALL" && entBands === 0) continue;   // hide empty rows in mode view
      rows.push(`<tr><td class="dx-ent">${esc(name)}</td>${cells.join("")}` +
                `<td class="dx-total">${entBands}</td></tr>`);
    }

    const head = `<tr><th>ENTITY (${rows.length})</th>` +
      bands.map((b) => `<th>${b.replace("m", "")}</th>`).join("") + `<th>Σ</th></tr>`;
    const totals = `<tr class="dx-totals"><td class="dx-ent">band totals</td>` +
      bands.map((b) => `<td>${bandTotals[b] || ""}</td>`).join("") +
      `<td class="dx-total">${slotTotal}</td></tr>`;

    $("dxcc-table").innerHTML = rows.length
      ? head + rows.join("") + totals
      : `<tr><td class="dim" style="padding:20px">` +
        (names.length ? "no entities match the filter"
         : "No QSOs imported yet — use ⬆ IMPORT ADIF (top right) or add your log " +
           "under 'Log files to auto-import' in ⚙ SETUP.") + `</td></tr>`;

    const st = d.stats || {};
    $("dxcc-stats").textContent =
      `${names.length} entities · ${slotTotal} band-slot${slotTotal === 1 ? "" : "s"}` +
      ` (${confTotal} confirmed)` +
      (this.mode !== "ALL" ? ` · ${this.mode} only` : "") +
      (st.slots != null && this.mode === "ALL" && !this.search
        ? ` · ${st.slots} mode-slots in log` : "");
  },
};

DxccTable.init();
