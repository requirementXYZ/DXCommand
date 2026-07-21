"use strict";
/* Station Setup panel: switch demo / OmniRig / cluster / WSJT-X at runtime.
   Reads current config from GET /api/config, applies via POST /api/config
   (server persists to config.json and hot-swaps the services). */

const Settings = {
  open() {
    fetch("/api/config").then((r) => r.json()).then((c) => {
      $("set-call").value = c.callsign || "";
      $("set-grid").value = c.grid || "";
      $("set-rig").value = c.rig.backend === "omnirig"
        ? "omnirig" + (c.rig.rig_number === 2 ? "2" : "1") : "simulator";
      $("set-cluster").value = c.cluster.simulate ? "sim" : "telnet";
      $("set-cluster-host").value = c.cluster.host || "";
      $("set-cluster-port").value = c.cluster.port || 23;
      $("set-wsjtx").value = c.wsjtx.simulate ? "sim" : (c.wsjtx.enabled ? "udp" : "off");
      $("set-wsjtx-port").value = c.wsjtx.udp_port || 2237;
      $("set-rbn").checked = !c.rbn || c.rbn.enabled !== false;
      $("set-logsync").value = ((c.logsync || {}).paths || []).join("\n");
      Settings.refreshEnabled();
      $("settings-overlay").hidden = false;
    });
  },

  close() { $("settings-overlay").hidden = true; },

  refreshEnabled() {
    const clusterSim = $("set-cluster").value === "sim";
    $("set-cluster-host").disabled = clusterSim;
    $("set-cluster-port").disabled = clusterSim;
    $("set-wsjtx-port").disabled = $("set-wsjtx").value !== "udp";
  },

  preset(live) {
    $("set-rig").value = live ? "omnirig1" : "simulator";
    $("set-cluster").value = live ? "telnet" : "sim";
    $("set-wsjtx").value = live ? "udp" : "sim";
    Settings.refreshEnabled();
  },

  async save() {
    const rigSel = $("set-rig").value;
    const body = {
      callsign: $("set-call").value.trim() || "N0CALL",
      grid: $("set-grid").value.trim() || "IO95rj",
      rig: {
        backend: rigSel === "simulator" ? "simulator" : "omnirig",
        rig_number: rigSel === "omnirig2" ? 2 : 1,
      },
      cluster: {
        simulate: $("set-cluster").value === "sim",
        host: $("set-cluster-host").value.trim() || "dxc.ve7cc.net",
        port: parseInt($("set-cluster-port").value, 10) || 23,
      },
      wsjtx: {
        simulate: $("set-wsjtx").value === "sim",
        enabled: $("set-wsjtx").value !== "off",
        udp_port: parseInt($("set-wsjtx-port").value, 10) || 2237,
      },
      rbn: { enabled: $("set-rbn").checked },
      logsync: { paths: $("set-logsync").value.split("\n")
                   .map((s) => s.trim()).filter(Boolean) },
    };
    const btn = $("settings-save");
    btn.disabled = true;
    btn.textContent = "APPLYING…";
    try {
      const res = await post("/api/config", body);
      if (!res.ok) {
        toast(`Settings rejected: ${res.error || "unknown error"}`, "alert");
        return;
      }
      const cty = res.cty && res.cty.source === "cty.dat"
        ? ` · country list: ${res.cty.entities} entities` : "";
      toast((body.rig.backend === "omnirig"
        ? `Applied — OmniRig Rig ${body.rig.rig_number} active`
        : "Applied — demo (simulated rig) active") + cty);
      if (!body.cluster.simulate && body.callsign === "N0CALL") {
        toast("⚠ DX clusters reject the N0CALL placeholder — enter your real callsign in SETUP", "alert");
      }
      Settings.close();
      // Fresh sources mean fresh spots/decodes; reload keeps every panel consistent.
      setTimeout(() => location.reload(), 900);
    } catch (e) {
      toast(`Settings failed: ${e.message}`, "alert");
    } finally {
      btn.disabled = false;
      btn.textContent = "💾 SAVE & APPLY";
    }
  },
};

$("btn-settings").onclick = Settings.open;
$("settings-close").onclick = Settings.close;
$("settings-save").onclick = Settings.save;
$("preset-demo").onclick = () => Settings.preset(false);
$("preset-live").onclick = () => Settings.preset(true);
$("set-cluster").onchange = Settings.refreshEnabled;
$("set-wsjtx").onchange = Settings.refreshEnabled;
$("settings-overlay").addEventListener("click", (e) => {
  if (e.target.id === "settings-overlay") Settings.close();
});
