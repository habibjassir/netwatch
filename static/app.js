const grid = document.getElementById("grid");
const empty = document.getElementById("empty");
const statusEl = document.getElementById("status");
const scanBtn = document.getElementById("scan-btn");
const autoEl = document.getElementById("auto");
const filterEl = document.getElementById("filter");

let snapshot = { devices: [], network: {}, scanned_hosts: 0, duration_ms: 0, scanned_at: 0 };
let timer = null;

function fmtTime(epoch) {
  if (!epoch) return "—";
  return new Date(epoch * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function render() {
  const q = filterEl.value.trim().toLowerCase();
  const devices = snapshot.devices.filter((d) => {
    if (!q) return true;
    return [d.ip, d.mac, d.hostname, d.vendor].filter(Boolean).join(" ").toLowerCase().includes(q);
  });

  const net = snapshot.network || {};
  document.getElementById("network-title").textContent = net.network || "No subnet";
  document.getElementById("network-lede").textContent = net.hostname
    ? `${net.hostname} on ${net.os || "this OS"} is watching ${net.network}.`
    : "Waiting for the first scan.";
  document.getElementById("iface").textContent = net.interface || "—";
  document.getElementById("self").textContent = net.local_ip || "—";
  document.getElementById("gateway").textContent = net.gateway || "—";
  document.getElementById("last-scan").textContent = fmtTime(snapshot.scanned_at);
  document.getElementById("stat-online").textContent = String(snapshot.devices.filter((d) => d.reachable).length);
  document.getElementById("stat-mac").textContent = String(snapshot.devices.filter((d) => d.mac).length);
  document.getElementById("stat-probed").textContent = String(snapshot.scanned_hosts || 0);
  document.getElementById("stat-ms").textContent = snapshot.duration_ms ? `${(snapshot.duration_ms / 1000).toFixed(1)}s` : "—";

  grid.innerHTML = "";
  empty.hidden = devices.length > 0;
  for (const d of devices) {
    const card = document.createElement("article");
    card.className = "card";
    if (d.is_self) card.classList.add("self");
    if (d.is_gateway) card.classList.add("gateway");

    const badges = [];
    badges.push(`<span class="badge ${d.reachable ? "up" : "stale"}">${d.reachable ? "online" : "arp only"}</span>`);
    if (d.is_self) badges.push('<span class="badge self">this device</span>');
    if (d.is_gateway) badges.push('<span class="badge gw">gateway</span>');

    card.innerHTML = `
      <div class="row">
        <span class="ip">${d.ip}</span>
        <span>${badges.join(" ")}</span>
      </div>
      <p class="host">${d.hostname || "Unnamed host"}</p>
      <p class="mac">${d.mac || "MAC not in ARP yet"}</p>
      <p class="vendor">${d.vendor || "Vendor unknown"}</p>
    `;
    grid.appendChild(card);
  }
}

async function scan(refresh) {
  scanBtn.disabled = true;
  statusEl.textContent = refresh ? "Probing the subnet…" : "Loading last snapshot…";
  try {
    const res = await fetch(`/api/devices${refresh ? "?refresh=true" : ""}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    snapshot = await res.json();
    statusEl.textContent = `Found ${snapshot.devices.length} host${snapshot.devices.length === 1 ? "" : "s"}.`;
    render();
  } catch (err) {
    statusEl.textContent = `Scan failed: ${err.message}`;
  } finally {
    scanBtn.disabled = false;
  }
}

function schedule() {
  clearInterval(timer);
  if (autoEl.checked) {
    timer = setInterval(() => scan(true), 30000);
  }
}

scanBtn.addEventListener("click", () => scan(true));
autoEl.addEventListener("change", schedule);
filterEl.addEventListener("input", render);

scan(true);
schedule();
