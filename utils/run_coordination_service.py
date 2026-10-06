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

hostname = socket.gethostname()
url = f"http://{hostname}:{args.port}"

print(f"Starting Coordination Service on this machine ({hostname}), port {args.port}.")
print()
print("On the OTHER machine (Source or Target, whichever this isn't), set:")
print(f"    DDA_COORDINATION_SERVICE_URL={url}")
print()
print(f"Confirm reachability from there first with:")
print(f'    Invoke-RestMethod -Uri "{url}/health"')
print("(should return status: ok -- if it doesn't, check firewall/network, not the code)")
print()

uvicorn.run("coordination_service.app:app", host="0.0.0.0", port=args.port)
