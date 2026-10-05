"""
LoggerFactory: idempotent loguru setup for live, colored console logging plus persisted
log files -- green for success, red for error/failure, using loguru's own default level
colors (SUCCESS is green, ERROR/CRITICAL are red) rather than inventing custom levels.

There is no pytest runner wired up yet (tests/ is still stub-only -- see
PROJECT_PLAN.md; every flow today runs as a standalone tools/_test_*.py script, not
through pytest), so this is how pass/fail is surfaced in the meantime: live colored
console output plus a rotating log file, not a pytest report.
"""

import sys
import threading
from pathlib import Path

from loguru import logger

LOG_DIR = Path(__file__).resolve().parent.parent / "reports" / "output" / "logs"

_CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "<cyan>{extra[role]}</cyan> | <level>{message}</level>"
)
_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[role]} | {message}"


class LoggerFactory:
    _console_configured = False
    _role_sinks: set = set()
    _lock = threading.RLock()

    @classmethod
    def ensure_console(cls) -> None:
        """Idempotent -- safe to call from any module that logs (e.g.
        components/base_component.py) without needing a role yet."""
        if cls._console_configured:
            return
        logger.remove()  # drop loguru's default stderr sink so we control format/color
        logger.configure(extra={"role": "-"})  # default for any unbound log call
        logger.add(sys.stderr, level="DEBUG", format=_CONSOLE_FORMAT, colorize=True)

        # Unfiltered file sink -- captures everything regardless of role binding, so
        # component-level logs (which don't bind a role -- see components/base_component.py)
        # are never lost to file even before a flow calls get_logger(role).
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logger.add(
            LOG_DIR / "automation.log",
            level="DEBUG",
            format=_FILE_FORMAT,
            rotation="10 MB",
            retention=5,
            enqueue=True,
        )
        cls._console_configured = True

    @classmethod
    def get_logger(cls, role: str):
        """Returns a loguru logger bound with extra={'role': role}. Idempotent per role --
        a role's own filtered log file is only added once even if called repeatedly
        (same idempotency pattern as factory/driver_factory.py's DriverFactory).
        """
        with cls._lock:
            cls.ensure_console()
            if role not in cls._role_sinks:
                logger.add(
                    LOG_DIR / f"{role}.log",
                    level="DEBUG",
                    format=_FILE_FORMAT,
                    rotation="10 MB",
                    retention=5,
                    enqueue=True,
                    filter=lambda record, _role=role: record["extra"].get("role") == _role,
                )
                cls._role_sinks.add(role)
        return logger.bind(role=role)
