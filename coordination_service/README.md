# Coordination Service

Small relay used to hand the pairing code (and later signals) between the independent
Source and Target automation invocations. See PROJECT_PLAN.md Sec 4.6 for the design.

Nothing about this service is role-specific -- it can run on the Source machine, the
Target machine, or a separate third host. Whichever machine runs it, the OTHER machine
just needs `DDA_COORDINATION_SERVICE_URL` pointed at it.

**Run it** (prints the exact address to give the other machine):

```
python utils/run_coordination_service.py [--port 8000]
```

Or directly, if you already know the address you want to use:

```
uvicorn coordination_service.app:app --host 0.0.0.0 --port 8000
```

**Address stability** (confirmed 2026-10-06): a plain Windows hostname
(`http://<hostname>:8000`) resolves across machines on the same LAN via NetBIOS/LLMNR by
default -- no DNS server, no manual IP lookup, and it survives the hosting machine's IP
changing via DHCP. Verified working end-to-end between two real, separate Windows
machines. If that's ever disabled by network policy, fall back to a DHCP
reservation/static IP for the hosting machine, or run this on a separate always-on host
-- either way, only `DDA_COORDINATION_SERVICE_URL` on the other machine's `.env` needs to
change, nothing in the code.

**Confirm reachability from the other machine before relying on it**:

```
Invoke-RestMethod -Uri "http://<hostname>:8000/health"
```

Should return `status: ok`. If it doesn't, that's a network/firewall issue on that LAN,
not a code issue -- troubleshoot the connection before assuming anything's broken here.
