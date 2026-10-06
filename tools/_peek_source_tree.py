import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from factory import capabilities as caps
from factory.config import WINAPPDRIVER_URL
from factory.driver_factory import WinAppDriverSession
from factory.session import _find_main_window_hwnd

hwnd = _find_main_window_hwnd("DellDataAssistant")
print("hwnd:", hwnd)

resp = requests.post(f"{WINAPPDRIVER_URL}/session", json=caps.app_attach_capabilities(hwnd), timeout=30)
resp.raise_for_status()
session = WinAppDriverSession(WINAPPDRIVER_URL, resp.json()["sessionId"])

source = session.page_source
names = re.findall(r'Name="([^"]{2,80})"', source)
# Dedup while preserving order, skip empty/pure-whitespace
seen = []
for n in names:
    if n.strip() and n not in seen:
        seen.append(n)
print("Distinct Name values on screen:")
for n in seen:
    print(" -", n)

session.quit()
