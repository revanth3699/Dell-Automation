"""Offline verification of PairingCodeScreen's interpolation + cropped-OCR logic,
using REAL data captured earlier: tools/_phase0_source_code_screenshot.png (code
"475672", box 4 -- digit '7' -- confirmed missing from UIA that read) and the real
on-screen rects for boxes 0,1,2,3,5 from that same session's tree dump.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.source.pairing_code_screen import PairingCodeScreen

# Real rects captured from tools/_phase0_source_tree_dump_code.xml (same session as the
# screenshot below): x="379/457/535/613/769" y="320" width="52" height="75" for boxes
# 0,1,2,3,5 (box 4, the missing one, has no rect -- that's exactly the gap we're testing).
known_digits = {0: "4", 1: "7", 2: "5", 3: "6", 5: "2"}
known_rects = {
    0: {"x": 379, "y": 320, "width": 52, "height": 75},
    1: {"x": 457, "y": 320, "width": 52, "height": 75},
    2: {"x": 535, "y": 320, "width": 52, "height": 75},
    3: {"x": 613, "y": 320, "width": 52, "height": 75},
    5: {"x": 769, "y": 320, "width": 52, "height": 75},
}
expected_full_code = "475672"  # confirmed by direct visual read of the screenshot earlier

# PairingCodeScreen normally talks to a live WinAppDriver session -- we only need its
# pure-logic methods here (_interpolate_missing_rects, _read_via_cropped_ocr), so
# construct it with session=None and monkeypatch get_screenshot_as_png to read our
# saved real screenshot file instead of hitting a live app.
screenshot_path = Path(__file__).resolve().parent / "_phase0_source_code_screenshot.png"
screenshot_bytes = screenshot_path.read_bytes()


class FakeSession:
    def get_screenshot_as_png(self) -> bytes:
        return screenshot_bytes


screen = PairingCodeScreen.__new__(PairingCodeScreen)
screen._session = FakeSession()

interpolated = screen._interpolate_missing_rects(known_rects)
print("Interpolated rect for missing position(s):", interpolated)

assert set(interpolated.keys()) == {4}, f"Expected only position 4 missing, got {interpolated.keys()}"

recovered_digit = screen._read_via_neighbor_crop_ocr(4, known_rects, known_digits)
print(f"Neighbor-crop OCR recovered digit for position 4: {recovered_digit!r}")
print(f"Expected digit (from known code {expected_full_code}): {expected_full_code[4]!r}")

if recovered_digit == expected_full_code[4]:
    print("PASS: cropped-box OCR correctly recovered the missing digit.")
else:
    print("FAIL: cropped-box OCR did not recover the correct digit.")

full_code = dict(known_digits)
if recovered_digit:
    full_code[4] = recovered_digit
if len(full_code) == 6:
    reconstructed = "".join(full_code[i] for i in range(6))
    print(f"Reconstructed full code: {reconstructed} (expected {expected_full_code})")
