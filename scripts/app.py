from __future__ import annotations

from pathlib import Path
from threading import Lock

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from scanner import detect_network, scan

ROOT = Path(__file__).parent
STATIC = ROOT / "static"

app = FastAPI(title="Netwatch")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_lock = Lock()
_cache: dict | None = None


@app.get("/")
def landing() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/network")
def network() -> dict:
    return detect_network()


@app.get("/api/devices")
def devices(refresh: bool = False) -> dict:
    global _cache
    with _lock:
        if refresh or _cache is None:
            _cache = scan()
        return _cache
