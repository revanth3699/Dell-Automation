"""
Manages the GlassFloor entitlement mock server (SupportAssistRaceHarness/server.js) used
to test the Target PC app's entitlement flow -- see PROJECT_PLAN.md Sec 5.3a and
tools/phase0_inspection_notes.md ("GlassFloor entitlement mock-server launch"). Confirmed
working against the Release build in that spike; this module makes the same recipe
reusable.
"""

import socket
import subprocess
import time
from pathlib import Path
from typing import Optional

from factory.config import MOCK_SERVER_DEFAULT_PORT as DEFAULT_PORT


def _port_is_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class MockServer:
    def __init__(self, process: subprocess.Popen, port: int, secret: str, cert_path: str):
        self.process = process
        self.port = port
        self.secret = secret
        self.cert_path = cert_path

    @property
    def server_address(self) -> str:
        return f"127.0.0.1:{self.port}"

    def is_running(self) -> bool:
        return self.process.poll() is None

    def stop(self) -> None:
        if self.is_running():
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()


def start_mock_server(
    package_path: str,
    secret: str,
    port: int = DEFAULT_PORT,
    startup_timeout: float = 15.0,
    node_path: str = "node",
) -> MockServer:
    """Starts SupportAssistRaceHarness/server.js with the given scenario secret. Returns
    a MockServer handle once the port is confirmed listening. Raises RuntimeError if it
    doesn't come up in time (e.g. certs expired, port already in use, node missing).
    """
    harness_dir = Path(package_path) / "SupportAssistRaceHarness"
    server_js = harness_dir / "server.js"
    cert_path = harness_dir / "cert.pfx"
    if not server_js.is_file():
        raise FileNotFoundError(f"server.js not found under {harness_dir}")
    if not cert_path.is_file():
        raise FileNotFoundError(f"cert.pfx not found under {harness_dir}")

    if _port_is_open("127.0.0.1", port):
        raise RuntimeError(
            f"Port {port} is already in use -- stop whatever's using it "
            "(a previous mock server run?) before starting a new one."
        )

    process = subprocess.Popen(
        [node_path, "server.js", str(port), secret],
        cwd=str(harness_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.monotonic() + startup_timeout
    while time.monotonic() < deadline:
        if _port_is_open("127.0.0.1", port):
            return MockServer(process, port, secret, str(cert_path))
        if process.poll() is not None:
            raise RuntimeError(
                f"server.js exited immediately (code {process.returncode}) -- "
                "check certs haven't expired and Node.js is installed."
            )
        time.sleep(0.5)

    process.kill()
    raise RuntimeError(f"Mock server did not start listening on port {port} within {startup_timeout}s")
