"""
Interactive Target PC launcher: checks + auto-installs prerequisites, prompts for the
build path, launches the app, and attaches a WinAppDriver session.

Target-only -- Source's launch flow is still undetermined (see PROJECT_PLAN.md Sec 10,
open item 1). Usage:

    python tools/launch_target_app.py [--build-path PATH]

With --with-mock-server, also starts the GlassFloor entitlement mock server first (see
PROJECT_PLAN.md Sec 5.3a) and launches the app with the matching CLI args:

    python tools/launch_target_app.py --with-mock-server \
        [--build-path PATH] [--mock-server-package PATH] [--secret my-secret-active]

Any path/secret omitted on the command line is prompted for interactively.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.mock_server import start_mock_server
from utils.prerequisites import ensure_mock_server_prerequisites, ensure_target_prerequisites
from factory.session import MachineRole, Session


def _prompt_for_path(label: str) -> str:
    while True:
        raw = input(f"{label}: ").strip().strip('"')
        path = Path(raw)
        if path.exists():
            return str(path)
        print(f"  Not found: {raw!r} -- try again.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-path", help="Path to DellDataAssistant.TargetPc.exe (skips the prompt)")
    parser.add_argument("--with-mock-server", action="store_true",
                         help="Start the GlassFloor mock server first and launch the app against it")
    parser.add_argument("--mock-server-package", help="Path to the extracted GlassFloor-TestPackage folder")
    parser.add_argument("--secret", default="my-secret-active",
                         help="Mock server scenario secret (default: my-secret-active)")
    parser.add_argument("--port", type=int, default=8443, help="Mock server port (default: 8443)")
    args = parser.parse_args()

    print("Checking Target PC prerequisites...")
    ensure_target_prerequisites()

    build_path = args.build_path or _prompt_for_path("Path to DellDataAssistant.TargetPc.exe")

    app_arguments = None
    if args.with_mock_server:
        print("Checking mock server prerequisites...")
        node_path = ensure_mock_server_prerequisites()

        package_path = args.mock_server_package or _prompt_for_path(
            "Path to the extracted GlassFloor-TestPackage folder"
        )

        print(f"Starting mock server on port {args.port} with secret {args.secret!r}...")
        mock_server = start_mock_server(package_path, args.secret, args.port, node_path=node_path)
        print(f"Mock server listening on {mock_server.server_address}")

        app_arguments = [mock_server.secret, mock_server.cert_path, mock_server.server_address]

    print(f"Launching and attaching to: {build_path}")
    session = Session.get(MachineRole.TARGET, build_path=build_path, app_arguments=app_arguments)
    print(f"Attached. session_id={session.app.session_id}")
    return session


if __name__ == "__main__":
    main()
