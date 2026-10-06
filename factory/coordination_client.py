"""
CoordinationClient: the only channel through which the independent Source and Target
automation processes exchange a hand-off value (the pairing code today, and later any
similar signal -- e.g. "source ready to transfer") -- via the Coordination Service
(coordination_service/app.py). See PROJECT_PLAN.md Sec 4.6.

`key` is a generic string, not hardcoded to "pairing_code" -- reuse publish()/wait_for()
for later hand-offs rather than inventing a second mechanism.
"""

from typing import Optional

import requests
from loguru import logger

from factory.config import COORDINATION_SERVICE_URL
from factory.wait_utils import poll_until

# Shared key name for the pairing-code hand-off -- defined once here so
# flows/source/pairing_flow.py (publisher) and flows/target/pairing_flow.py (fetcher)
# can't drift apart on the literal string.
PAIRING_CODE_KEY = "pairing_code"


class CoordinationClient:
    def __init__(self, base_url: str = COORDINATION_SERVICE_URL):
        self.base_url = base_url.rstrip("/")

    def publish(self, run_id: str, key: str, value: str, timeout: float = 10.0) -> None:
        url = f"{self.base_url}/runs/{run_id}/{key}"
        logger.debug(f"CoordinationClient: PUT {url}")
        resp = requests.put(url, json={"value": value}, timeout=timeout)
        resp.raise_for_status()

    def _try_get(self, run_id: str, key: str, timeout: float) -> Optional[str]:
        url = f"{self.base_url}/runs/{run_id}/{key}"
        logger.debug(f"CoordinationClient: GET {url}")
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 404:
            logger.debug(f"CoordinationClient: GET {url} -- not published yet (404)")
            return None
        resp.raise_for_status()
        logger.debug(f"CoordinationClient: GET {url} -- got a value")
        return resp.json()["value"]

    def wait_for(self, run_id: str, key: str, timeout: float, poll_interval: float = 2.0) -> str:
        """Polls until a value is published, or raises TimeoutError. Network errors
        against the service (e.g. not reachable yet) are treated the same as "not
        published yet" and retried, not raised immediately -- the two independent
        processes may start in either order."""
        logger.info(
            f"CoordinationClient: starting to poll {self.base_url} for runs/{run_id}/{key} "
            f"every {poll_interval:.0f}s (timeout={timeout:.0f}s)"
        )
        return poll_until(
            lambda: self._try_get(run_id, key, timeout=10.0),
            timeout=timeout,
            interval=poll_interval,
            ignored_exceptions=(requests.exceptions.RequestException,),
        )
