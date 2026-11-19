"""Discover hosts on the current LAN (macOS / Linux)."""

from __future__ import annotations

import asyncio
import ipaddress
import platform
import re
import socket
import subprocess
import time
from dataclasses import asdict, dataclass
from typing import Any

OUI_HINTS: dict[str, str] = {
    "00:17:88": "Philips Hue",
    "00:1A:11": "Google",
    "00:1D:D8": "Microsoft",
    "00:21:6A": "Intel",
    "00:23:6C": "Apple",
    "00:24:E4": "Cisco",
    "00:25:00": "Apple",
    "00:26:BB": "Apple",
    "00:50:56": "VMware",
    "04:D3:B0": "Intel",
    "10:DD:B1": "Apple",
    "18:65:90": "Apple",
    "20:C9:D0": "Apple",
    "28:CF:E9": "Apple",
    "34:36:3B": "Apple",
    "38:F9:D3": "Apple",
    "3C:22:FB": "Apple",
    "40:B0:76": "Apple",
    "44:D8:84": "Apple",
    "48:D7:05": "Apple",
    "4C:32:75": "Apple",
    "50:ED:3C": "Amazon",
    "52:54:00": "QEMU/KVM",
    "54:E4:3A": "Apple",
    "58:55:CA": "Apple",
    "60:03:08": "Apple",
    "64:A3:CB": "Apple",
    "68:96:7B": "Apple",
    "6C:96:CF": "Apple",
    "70:56:81": "Apple",
    "78:31:C1": "Apple",
    "7C:04:D0": "Apple",
    "80:E6:50": "Apple",
    "88:66:A5": "Apple",
    "8C:85:90": "Apple",
    "90:72:40": "Apple",
    "98:01:A7": "Apple",
    "A4:83:E7": "Apple",
    "A8:60:B6": "Apple",
    "AC:87:A3": "Apple",
    "B0:65:BD": "Apple",
    "B8:09:8A": "Apple",
    "BC:D0:74": "Apple",
    "C8:69:CD": "Apple",
    "CC:29:F5": "Apple",
    "D0:03:4B": "Apple",
    "D4:61:9D": "Apple",
    "DC:A9:04": "Apple",
    "E0:AC:CB": "Apple",
    "F0:18:98": "Apple",
    "F4:0F:24": "Apple",
    "FC:25:3F": "Apple",
}

_ARP_LINE = re.compile(
    r"\((?P<ip>\d+\.\d+\.\d+\.\d+)\)\s+at\s+(?P<mac>[0-9a-fA-F:.-]+)"
)
_INET_LINE = re.compile(
    r"inet\s+(?P<ip>\d+\.\d+\.\d+\.\d+).*netmask\s+(?P<mask>0x[0-9a-fA-F]+|\d+\.\d+\.\d+\.\d+)"
)


@dataclass
class Device:
    ip: str
    mac: str | None
    hostname: str | None
    vendor: str | None
    is_self: bool
    is_gateway: bool
    reachable: bool


def _run(args: list[str], timeout: float = 4.0) -> str:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    return result.stdout or ""


def _normalize_mac(raw: str) -> str | None:
    value = raw.strip().lower().replace("-", ":")
    if value in {"(incomplete)", "incomplete", "ff:ff:ff:ff:ff:ff"}:
        return None
    parts = value.split(":")
    if len(parts) == 6:
        return ":".join(p.zfill(2) for p in parts)
    return None


def _vendor_for(mac: str | None) -> str | None:
    if not mac:
        return None
    prefix = mac[:8].upper()
    return OUI_HINTS.get(prefix)


def _hex_netmask_to_dotted(mask: str) -> str:
    if mask.startswith("0x"):
        n = int(mask, 16)
        return socket.inet_ntoa(n.to_bytes(4, "big"))
    return mask


def detect_network() -> dict[str, Any]:
    iface = None
    gateway = None
    route_out = _run(["route", "-n", "get", "default"])
    for line in route_out.splitlines():
        line = line.strip()
        if line.startswith("gateway:"):
            gateway = line.split(":", 1)[1].strip()
        elif line.startswith("interface:"):
            iface = line.split(":", 1)[1].strip()

    if not iface:
        for candidate in ("en0", "en1", "eth0", "wlan0"):
            if _run(["ifconfig", candidate]):
                iface = candidate
                break

    local_ip = None
    netmask = None
    if iface:
        cfg = _run(["ifconfig", iface])
        match = _INET_LINE.search(cfg)
        if match:
            local_ip = match.group("ip")
            netmask = _hex_netmask_to_dotted(match.group("mask"))

    if not local_ip:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("1.1.1.1", 80))
            local_ip = sock.getsockname()[0]
        except OSError:
            local_ip = "127.0.0.1"
        finally:
            sock.close()

    cidr = None
    network = None
    if local_ip and netmask:
        try:
            iface_net = ipaddress.IPv4Interface(f"{local_ip}/{netmask}")
            network = str(iface_net.network)
            cidr = iface_net.network.prefixlen
        except ValueError:
            pass

    if cidr is None:
        cidr = 24
        network = str(ipaddress.IPv4Network(f"{local_ip}/24", strict=False))

    return {
        "hostname": socket.gethostname(),
        "interface": iface,
        "local_ip": local_ip,
        "gateway": gateway,
        "cidr": cidr,
        "network": network,
        "os": platform.system(),
    }


def _parse_arp() -> dict[str, str]:
    table: dict[str, str] = {}
    output = _run(["arp", "-an"])
    for line in output.splitlines():
        match = _ARP_LINE.search(line)
        if not match:
            continue
        mac = _normalize_mac(match.group("mac"))
        if mac:
            table[match.group("ip")] = mac
    return table


def _lookup_hostname(ip: str) -> str | None:
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        return name.rstrip(".")
    except (socket.herror, socket.gaierror, OSError):
        return None


async def _ping(ip: str, sem: asyncio.Semaphore) -> bool:
    async with sem:
        proc = await asyncio.create_subprocess_exec(
            "ping",
            "-c",
            "1",
            "-W",
            "200" if platform.system() == "Darwin" else "1",
            ip,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0


async def _sweep(hosts: list[str], limit: int = 64) -> set[str]:
    sem = asyncio.Semaphore(limit)
    results = await asyncio.gather(*(_ping(ip, sem) for ip in hosts), return_exceptions=True)
    alive: set[str] = set()
    for ip, result in zip(hosts, results):
        if result is True:
            alive.add(ip)
    return alive


def _host_list(network: ipaddress.IPv4Network, local_ip: str, gateway: str | None) -> list[str]:
    if network.num_addresses > 512:
        network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
    hosts = [str(h) for h in network.hosts()]
    extras = [local_ip]
    if gateway:
        extras.append(gateway)
    for extra in extras:
        if extra not in hosts:
            hosts.append(extra)
    return hosts


def scan() -> dict[str, Any]:
    started = time.time()
    net = detect_network()
    local_ip = net["local_ip"]
    gateway = net["gateway"]
    network = ipaddress.IPv4Network(net["network"], strict=False)

    hosts = _host_list(network, local_ip, gateway)
    alive = asyncio.run(_sweep(hosts))
    arp = _parse_arp()

    ips = set(alive) | set(arp) | {local_ip}
    if gateway:
        ips.add(gateway)

    devices: list[Device] = []
    for ip in sorted(ips, key=lambda value: ipaddress.IPv4Address(value)):
        addr = ipaddress.IPv4Address(ip)
        if addr.is_multicast or addr.is_reserved or addr.is_unspecified or addr.is_loopback:
            continue
        mac = arp.get(ip)
        if ip == local_ip and not mac:
            mac = "local"
        reachable = ip in alive or ip == local_ip
        devices.append(
            Device(
                ip=ip,
                mac=None if mac == "local" else mac,
                hostname=_lookup_hostname(ip),
                vendor="This machine" if ip == local_ip else _vendor_for(mac if mac != "local" else None),
                is_self=ip == local_ip,
                is_gateway=bool(gateway and ip == gateway),
                reachable=reachable,
            )
        )

    devices.sort(key=lambda d: (not d.is_self, not d.is_gateway, not d.reachable, ipaddress.IPv4Address(d.ip)))

    return {
        "network": net,
        "scanned_hosts": len(hosts),
        "duration_ms": int((time.time() - started) * 1000),
        "scanned_at": int(time.time()),
        "devices": [asdict(d) for d in devices],
    }
