# Netwatch usage guide

Netwatch is a local-only web dashboard that lists devices on the **same LAN as the computer running it**. Open the landing page, scan the subnet, and watch which hosts reply to ping or still appear in the ARP table.

It does not scan the internet, other VLANs, or networks you are not currently attached to.

---

## Start the app

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser on that same machine.

| Requirement | Notes |
| --- | --- |
| Python 3.11+ | Tested with 3.11 |
| macOS or Linux | Uses `route`, `ifconfig`, `ping`, and `arp` |
| Same Wi-Fi / Ethernet as the devices | Guest Wi-Fi or client isolation will hide other hosts |

Stop the server with `Ctrl+C` in the terminal.

---

## Using the landing page

The page loads a **fresh scan automatically**. While it runs, the status line reads “Probing the subnet…” and **Scan now** is disabled. A typical `/24` finishes in about five seconds.

### Header

- **Auto-scan** — when checked (default), Netwatch repeats a full probe every **30 seconds**. Uncheck it to freeze the last result.
- **Scan now** — runs a probe immediately, ignoring the timer.

### Current LAN

The large CIDR (for example `192.168.1.0/24`) is the subnet of the default network interface.

| Field | Meaning |
| --- | --- |
| **Interface** | OS name of the default NIC (`en0`, `eth0`, …) |
| **This host** | IPv4 address of the machine running Netwatch |
| **Gateway** | Default-route gateway, usually the router |
| **Last scan** | Local time of the latest completed probe |

### Summary counts

| Stat | Meaning |
| --- | --- |
| **Online** | Hosts that answered ICMP ping (plus this machine, which is always treated as reachable) |
| **Known MAC** | Hosts with a MAC address in the ARP table |
| **Hosts probed** | How many addresses were pinged (all usable hosts in the subnet, capped at a `/24` if the prefix is larger) |
| **Scan time** | How long that probe took |

### Device grid

Each card is one IPv4 host. Cards are ordered: this machine, then the gateway, then other online hosts, then ARP-only hosts, all by IP.

**Filter** matches a substring of IP, hostname, MAC, or vendor. It does not re-scan; it only hides cards already in the last snapshot.

If nothing matches, the page shows “No devices matched that filter.”

---

## Features

### Live LAN identity

On each scan Netwatch reads the default route and the interface address/netmask, then shows the hostname of this computer and the OS (`Darwin` on macOS, `Linux` on Linux).

### Ping + ARP discovery

1. Ping every usable address in the current subnet (concurrently).
2. Read the kernel ARP table (`arp -an`).
3. Merge ping replies, ARP entries, this host, and the gateway.
4. Drop multicast, loopback, unspecified, and reserved addresses (so mDNS `224.0.0.251` does not appear as a device).

A host can show up even if it did not answer ping, as long as the OS still has an ARP entry for it.

### Status badges

| Badge | Meaning |
| --- | --- |
| **online** | Replied to ping (or is this machine) |
| **arp only** | Seen in ARP, no ping reply this scan — often a phone in power-save, a firewalled host, or a stale cache entry |
| **this device** | The computer running Netwatch |
| **gateway** | Default-route gateway |

The **this device** and **gateway** cards also use a distinct border color.

### Hostname

Netwatch tries reverse DNS (`PTR`) for each IP. Home routers often have no records, so many cards say **Unnamed host**. That is expected, not a failed scan.

### MAC address

Taken from ARP after the ping sweep. If a host never talked on L2, you may see **MAC not in ARP yet**.

### Vendor hint

The first three octets of the MAC are compared to a small built-in list (common Apple prefixes, a few others). Unknown prefixes show **Vendor unknown**. This machine is labeled **This machine** instead of a vendor.

Vendor hints are not a full IEEE OUI database.

### Cached scan on the server

The first request (or any request with `refresh=true`) runs a probe and stores the result in memory. Later requests without refresh return that snapshot. The landing page always requests `refresh=true` on load, on **Scan now**, and on each auto-scan tick.

---

## HTTP API

Useful if you want to script against the same data the page uses.

### `GET /`

The landing page.

### `GET /api/network`

Fast metadata only: hostname, interface, local IP, gateway, CIDR, network, OS. Does not ping the subnet.

### `GET /api/devices`

Returns the last scan. Runs a new scan if none exists yet.

### `GET /api/devices?refresh=true`

Always runs a new probe. This is what the UI uses.

Example response shape:

```json
{
  "network": {
    "hostname": "MacBook-Air.local",
    "interface": "en0",
    "local_ip": "192.168.1.80",
    "gateway": "192.168.1.254",
    "cidr": 24,
    "network": "192.168.1.0/24",
    "os": "Darwin"
  },
  "scanned_hosts": 254,
  "duration_ms": 5200,
  "scanned_at": 1788202181,
  "devices": [
    {
      "ip": "192.168.1.80",
      "mac": "50:de:06:be:23:e4",
      "hostname": null,
      "vendor": "This machine",
      "is_self": true,
      "is_gateway": false,
      "reachable": true
    }
  ]
}
```

---

## What you will not see

- Devices on another SSID, VLAN, or guest network with client isolation
- Hosts that ignore ICMP and have no ARP entry
- IPv6-only neighbors (discovery is IPv4 only)
- Historical “last seen” beyond the current snapshot
- Traffic, ports, or services on each host

Sleeping phones and IoT gadgets often flip between **online** and **arp only** from scan to scan. That is normal.

---

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| Page stuck on “Detecting subnet…” | Confirm uvicorn is running and the browser is on `http://127.0.0.1:8000` |
| **Scan failed** | Check the terminal for Python errors; ping/`arp` must be available |
| Only this machine appears | Client isolation, VPN, or a `/32` path — connect to the same LAN without a tunnel |
| Scan takes a long time | Large subnets are capped at `/24`; still, ICMP timeouts add up if the network is slow |
| Port 8000 already in use | Stop the other process or start uvicorn with `--port 8001` |
