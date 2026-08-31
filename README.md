# Netwatch

Landing page that lists devices on the current local network.

How to use the dashboard, what each badge means, and the HTTP API: **[USAGE.md](USAGE.md)**.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

The first scan pings the active subnet (capped at a /24) and merges replies with the ARP table. Auto-scan repeats every 30 seconds.
