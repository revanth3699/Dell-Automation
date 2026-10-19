"""
WinAppDriver desired-capabilities builders.

WinAppDriver 1.2.1 rejects the modern Appium Python client's auto-`appium:`-prefixed
capabilities ("Bad capabilities. Specify either app or appTopLevelWindow"). Only the
legacy bare-key `desiredCapabilities` shape works -- confirmed via Phase 0 spike, see
PROJECT_PLAN.md Sec 4.3 and tools/phase0_inspection_notes.md.
"""


def app_launch_capabilities(app_exe_path: str, arguments: list[str] | None = None) -> dict:
    desired = {
        "app": app_exe_path,
        "platformName": "Windows",
        "deviceName": "WindowsPC",
    }
    if arguments:
        # WinAppDriver's appArguments capability takes one command-line string, not a
        # JSON array -- quote each argument ourselves so paths/secrets with spaces
        # survive, matching the quoting SV_HANDOFF.md's own launch examples use.
        desired["appArguments"] = " ".join(f'"{a}"' for a in arguments)
    return {"desiredCapabilities": desired}


def app_attach_capabilities(hwnd_hex: str) -> dict:
    return {
        "desiredCapabilities": {
            "appTopLevelWindow": hwnd_hex,
            "platformName": "Windows",
            "deviceName": "WindowsPC",
        }
    }


def desktop_session_capabilities() -> dict:
    """WinAppDriver's conventional desktop/shell session -- `app: "Root"` -- used for
    automating UI outside any one app's own window (here, a Windows toast notification,
    hosted by ShellExperienceHost/Action Center, not the Dell app's process). Never
    attempted in this codebase before this feature; whether this session can actually
    see toast/Action Center UI at all is an open risk, see the notification-automation
    plan's "Known open risks" #1.
    """
    return {
        "desiredCapabilities": {
            "app": "Root",
            "platformName": "Windows",
            "deviceName": "WindowsPC",
        }
    }
