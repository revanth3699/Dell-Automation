"""
Starts the Coordination Service on THIS machine and prints the exact address to give the
OTHER machine (whichever one is running Source or Target -- there's nothing role-specific
about hosting this service; it's a plain FastAPI relay, see coordination_service/app.py).

Usage:
    python utils/run_coordination_service.py [--port 8000]

Confirmed working (2026-10-06): a plain Windows hostname (e.g. http://REVANTH_DELL:8000)
resolves and is reachable from another machine on the same LAN via NetBIOS/LLMNR, no DNS
server or manual IP lookup needed. If that's ever disabled on your network, fall back to
a DHCP reservation/static IP for this machine, or run this on a separate always-on host --
either way, only the DDA_COORDINATION_SERVICE_URL env var on the OTHER machine needs to
change, nothing in the code.

Also prints this machine's actual LAN IP directly (not just the hostname) -- confirmed
needed live (2026-10-07): hostname resolution isn't always convenient/available on the
other machine, and the IP is the one unambiguous fallback that always works.
"""

import argparse
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--port", type=int, default=8000)
args = parser.parse_args()


def _get_lan_ip() -> str:
    """Returns this machine's actual outbound-facing LAN IP. Uses the standard
    UDP-connect trick: connecting a UDP socket never actually sends a packet (UDP is
    connectionless), it just asks the OS to pick the right local interface/IP for that
    route -- works even with no real internet access. Falls back to 127.0.0.1 (useless
    for another machine, but at least doesn't crash this script) if that somehow fails."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


hostname = socket.gethostname()
lan_ip = _get_lan_ip()
url = f"http://{hostname}:{args.port}"
ip_url = f"http://{lan_ip}:{args.port}"

# Confirmed live (2026-10-07): plain print() output sits in Python's stdout buffer and
# never reaches the terminal once uvicorn.run() below takes over and blocks forever --
# the buffer only flushes on a full process exit, which never happens here (same
# stdout-buffering issue seen elsewhere in this project). flush=True on every line (and
# an explicit sys.stdout.flush() as a belt-and-suspenders final call) forces it out
# immediately, before uvicorn's own banner prints.
print("=" * 70, flush=True)
print(f"Starting Coordination Service on this machine ({hostname}), port {args.port}.", flush=True)
print(flush=True)
print("On the OTHER machine (Source or Target, whichever this isn't), set:", flush=True)
print(f"    DDA_COORDINATION_SERVICE_URL={ip_url}      <-- IP, use this one first", flush=True)
print(f"    DDA_COORDINATION_SERVICE_URL={url}      <-- hostname, fallback if IP changes", flush=True)
print(flush=True)
print("Confirm reachability from there first with:", flush=True)
print(f'    Invoke-RestMethod -Uri "{ip_url}/health"', flush=True)
print("(should return status: ok -- if it doesn't, check firewall/network, not the code)", flush=True)
print("=" * 70, flush=True)
sys.stdout.flush()

uvicorn.run("coordination_service.app:app", host="0.0.0.0", port=args.port)
