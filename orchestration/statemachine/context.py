"""RunContext -- everything an action or setup step may need, in one object.

Actions are plain callables `perform(ctx, args)`. They reach the app through ctx.app
(the WinAppDriver session), the other machine only through ctx.coordination (never a
more direct path -- see CLAUDE.md "Both machines, one channel"), and keep any state they
need between steps in ctx.scratch (e.g. the browser-window snapshot taken before
clicking Continue, consumed by the sign-in action one step later).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunContext:
    role: str
    run_id: str
    session: Any                      # factory.session.Session (owns launch/teardown)
    app: Any                          # WinAppDriverSession attached to the app window
    coordination: Any                 # utils.coordination_client.CoordinationClient
    log: Any                          # loguru logger bound to the role
    env: dict[str, str] = field(default_factory=dict)      # credentials/paths from the environment
    scratch: dict[str, Any] = field(default_factory=dict)  # per-run working storage for actions
    scenario_name: str | None = None

    def require_env(self, name: str) -> str:
        value = self.env.get(name)
        if not value:
            raise RuntimeError(f"Required environment variable {name} is not set")
        return value
