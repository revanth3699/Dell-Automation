"""FastAPI relay: PUT/GET /runs/{run_id}/{key}, in-memory dict + file persistence.
See PROJECT_PLAN.md Sec 4.6.

Deployed once, reachable by both the Source and Target automation processes over the
LAN (run with --host 0.0.0.0, see README.md). Each process is a fully independent
invocation -- this service is the only channel between them. `key` is a generic string,
not hardcoded to "pairing_code", so later hand-offs (e.g. "source ready to transfer")
reuse the same mechanism.

Persistence is best-effort: every write is flushed to a JSON file so a service restart
doesn't lose an in-flight run's values. Not a database -- fine for this service's actual
job (short-lived hand-off values during one migration run), not meant to scale beyond
that.
"""

import json
import os
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Dell Data Assistant Coordination Service")

_STATE_PATH = Path(os.environ.get("DDA_COORDINATION_STATE_PATH", str(Path(__file__).resolve().parent / "state.json")))
_lock = threading.RLock()


def _load_state() -> dict:
    if not _STATE_PATH.exists():
        return {}
    try:
        return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict) -> None:
    try:
        _STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass  # best-effort persistence -- an in-memory-only write still succeeds


_state: dict = _load_state()


class PublishBody(BaseModel):
    value: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.put("/runs/{run_id}/{key}")
def publish(run_id: str, key: str, body: PublishBody) -> dict:
    with _lock:
        _state.setdefault(run_id, {})[key] = body.value
        _save_state(_state)
    return {"run_id": run_id, "key": key, "value": body.value}


@app.get("/runs/{run_id}/{key}")
def get_value(run_id: str, key: str) -> dict:
    with _lock:
        run = _state.get(run_id)
        value = run.get(key) if run else None
    if value is None:
        raise HTTPException(status_code=404, detail=f"No value published yet for runs/{run_id}/{key}")
    return {"run_id": run_id, "key": key, "value": value}
