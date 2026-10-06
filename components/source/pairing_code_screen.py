"""Source PC's pairing-code display screen ("Let's finish linking your PCs.") -- shows a
rotating 6-digit verification code that the Target PC must enter. Confirmed live
(2026-10-06) via Phase 0 spike against the real Source build.

Real app bug, confirmed reproducible across multiple code rotations: the 6-box ListView
("VerificationListControl") only ever exposes 5 of its 6 digit Text elements in the UI
Automation tree at any snapshot -- WHICH position is missing shifts between rotations,
not a fixed index. The app's own logs redact the code value
("VerificationCode: <PII>"), so log-scraping can't recover it either.

read_code() works around this with two layers of fallback, both cross-checked against
the UIA-confirmed digits before being trusted:
1. Whole-screenshot OCR (Windows' built-in engine, factory/ocr.py) -- cheap, worked
   reliably in initial testing.
2. Confirmed live (2026-10-06) on a SECOND machine: whole-screenshot OCR can fail to
   recognize the code's digits at all (the boxed digits are simply absent from the
   recognized text, likely a DPI/font-rendering difference between machines), while the
   missing UIA box is also consistently the SAME position every rotation on that
   machine (unlike the first machine, where it shifted). For this case, read_code()
   falls back further: interpolate the missing box's on-screen rectangle from the
   other boxes' confirmed rects (uniform spacing), then OCR a window spanning that box
   PLUS its immediate neighbor(s) -- confirmed live that Windows' OCR engine returns
   completely empty text for an isolated single-digit crop (verified directly: a crisp,
   clearly-legible digit produced zero recognized characters), but succeeds once given
   2-3 characters of surrounding context. The outer UI container for the missing
   position was also confirmed absent from the tree (not just its inner text run), so
   there's no deeper UI-element property left to query -- OCR is the only remaining
   path for that slot. The neighbor-crop result is self-verified against whichever
   digits are already known from UIA before being trusted.

Code rotates roughly every ~60s (confirmed via the app's own log timestamps -- see
tools/_phase0_source_spike.py's findings). Callers that need to keep a downstream
consumer (e.g. the Coordination Service, see flows/source/pairing_flow.py) supplied with
a currently-valid code must re-read and re-publish on that cadence, not read it once.
"""

import io
import re
import tempfile
import time
from pathlib import Path
from typing import Optional

from loguru import logger
from PIL import Image

from components.base_component import BaseComponent
from factory.ocr import recognize_text
from locators.source.pairing_code_screen import CANCEL_BUTTON_LOCATOR, CODE_BOX_LOCATORS, HEADING_LOCATOR


class PairingCodeScreen:
    def __init__(self, app_session):
        self._session = app_session
        self._heading = BaseComponent(app_session, *HEADING_LOCATOR, "PairingCodeHeading")
        self._boxes = [
            BaseComponent(app_session, *locator, f"VerificationCodeBox{i}", timeout=1.0)
            for i, locator in enumerate(CODE_BOX_LOCATORS)
        ]
        self._cancel_button = BaseComponent(app_session, *CANCEL_BUTTON_LOCATOR, "PairingCodeCancelButton")

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._heading.exists(timeout=timeout)

    def _read_via_uia(self) -> tuple:
        """Returns ({position: digit}, {position: rect}) for whichever of the 6 boxes
        are currently exposed in the UIA tree -- normally 5 of 6, sometimes all 6.
        Never raises for a missing box; that's the expected, confirmed-real case this
        whole class works around. Rects are captured alongside digits so a missing
        box's on-screen location can be interpolated later (_read_via_cropped_ocr)."""
        digits = {}
        rects = {}
        for i, box in enumerate(self._boxes):
            if not box.exists(timeout=0.3):
                continue
            try:
                element = box._find()
                text = element.get_text()
                rect = element.rect
            except Exception:
                continue
            if text and text.isdigit() and len(text) == 1:
                digits[i] = text
                rects[i] = rect
        return digits, rects

    def _read_via_ocr(self) -> Optional[str]:
        png_bytes = self._session.get_screenshot_as_png()
        tmp_path = Path(tempfile.gettempdir()) / "dda_pairing_code_ocr.png"
        tmp_path.write_bytes(png_bytes)
        try:
            text = recognize_text(str(tmp_path))
        except Exception as exc:
            logger.debug(f"OCR fallback failed: {exc}")
            return None
        # Confirmed live (2026-10-06): OCR sometimes reads each boxed digit as its own
        # token with whitespace between them (e.g. "4 7 5 6 7 2") rather than one
        # contiguous "475672" run, since each digit sits in its own bordered box on
        # screen -- a plain \d{6} match silently missed this every time. Allow optional
        # whitespace between digits and strip it from the result.
        match = re.search(r"\d(?:\s*\d){5}", text)
        if not match:
            logger.debug(f"OCR fallback: no 6-digit sequence found in recognized text: {text!r}")
            return None
        return re.sub(r"\s+", "", match.group(0))

    def _interpolate_missing_rects(self, rects: dict) -> dict:
        """Given {position: rect} for whichever boxes ARE known, computes an expected
        rect for each missing position (0-5) by linear interpolation along x -- the 6
        boxes are evenly spaced in a row, confirmed from live rect dumps. Needs at
        least 2 known positions to interpolate from; returns {} otherwise."""
        known = sorted(rects.keys())
        if len(known) < 2:
            return {}
        p_lo, p_hi = known[0], known[-1]
        x_lo, x_hi = rects[p_lo]["x"], rects[p_hi]["x"]
        dx = (x_hi - x_lo) / (p_hi - p_lo)
        sample = rects[p_lo]
        return {
            pos: {
                "x": x_lo + dx * (pos - p_lo),
                "y": sample["y"],
                "width": sample["width"],
                "height": sample["height"],
            }
            for pos in range(6)
            if pos not in rects
        }

    def _read_via_neighbor_crop_ocr(self, pos: int, rects: dict, known_digits: dict) -> Optional[str]:
        """OCRs a window spanning the missing box at `pos` plus its immediate left/right
        neighbor(s), not just the missing box alone.

        Confirmed live (2026-10-06): Windows' built-in OCR engine returns completely
        empty text for an isolated single-digit crop -- verified directly: a crisp,
        clearly-legible "7" crop produced zero recognized characters, repeatably, not a
        quality/resolution issue. It only succeeds once given 2-3 characters of
        surrounding context (a 3-box crop of "672" was read correctly). The result is
        self-verified against whichever neighbor digits are ALREADY known from UIA
        before being trusted -- if the recognized sequence doesn't agree with a known
        neighbor, something's wrong (stale screenshot, misaligned crop) and the read is
        discarded rather than risking a wrong digit.
        """
        interpolated = self._interpolate_missing_rects(rects)
        pos_rect = rects.get(pos) or interpolated.get(pos)
        if not pos_rect or len(rects) < 2:
            return None

        lo, hi = max(0, pos - 1), min(5, pos + 1)
        lo_rect = rects.get(lo) or interpolated.get(lo) or pos_rect
        hi_rect = rects.get(hi) or interpolated.get(hi) or pos_rect

        png_bytes = self._session.get_screenshot_as_png()
        image = Image.open(io.BytesIO(png_bytes))
        pad = 10
        left = max(0, int(lo_rect["x"]) - pad)
        top = max(0, int(pos_rect["y"]) - pad)
        right = int(hi_rect["x"] + hi_rect["width"]) + pad
        bottom = int(pos_rect["y"] + pos_rect["height"]) + pad
        crop = image.crop((left, top, right, bottom))
        crop = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
        tmp_path = Path(tempfile.gettempdir()) / "dda_pairing_code_neighbor_crop.png"
        crop.save(tmp_path)
        try:
            text = recognize_text(str(tmp_path))
        except Exception as exc:
            logger.debug(f"Neighbor-crop OCR failed: {exc}")
            return None

        found = re.findall(r"\d", text)
        expected_positions = list(range(lo, hi + 1))
        if len(found) != len(expected_positions):
            logger.debug(
                f"Neighbor-crop OCR: expected {len(expected_positions)} digits for "
                f"positions {expected_positions}, got {found!r} from recognized text {text!r}"
            )
            return None

        candidate = dict(zip(expected_positions, found))
        for p in expected_positions:
            if p in known_digits and known_digits[p] != candidate[p]:
                logger.debug(
                    f"Neighbor-crop OCR: candidate {candidate} disagrees with known "
                    f"digit at position {p} ({known_digits[p]!r}) -- discarding"
                )
                return None
        return candidate[pos]

    def read_code(self, attempts: int = 5, retry_delay: float = 0.4) -> str:
        """Returns the current 6-digit code. Combines the UIA fast path with two tiers
        of OCR fallback for whichever boxes the app's ListView doesn't reliably expose
        (see module docstring) -- confirmed live (2026-10-06) that more than one box can
        be missing at once, and that WHICH position(s) are missing can either shift
        between rotations (seen on one machine) or stay fixed (seen on another).
        Retries a few times before giving up, in case a read lands exactly mid-rotation
        (all 6 boxes briefly inconsistent) or an OCR cross-check disagrees."""
        last_digits: dict = {}
        for attempt in range(attempts):
            digits, rects = self._read_via_uia()
            if len(digits) == 6:
                code = "".join(digits[i] for i in range(6))
                logger.success(f"PairingCodeScreen: read code via UIA alone: {code}")
                return code

            last_digits = digits
            if digits:
                ocr_code = self._read_via_ocr()
                if ocr_code and len(ocr_code) == 6 and all(ocr_code[i] == digits[i] for i in digits):
                    logger.success(
                        f"PairingCodeScreen: read code via UIA ({len(digits)}/6) + "
                        f"whole-screenshot OCR fallback for the rest: {ocr_code}"
                    )
                    return ocr_code
                if ocr_code:
                    logger.debug(
                        f"PairingCodeScreen: whole-screenshot OCR read {ocr_code!r} "
                        f"disagrees with UIA-confirmed digits {digits!r} or is the wrong "
                        "length -- trying cropped-box OCR instead"
                    )

                missing_positions = [p for p in range(6) if p not in digits]
                recovered = dict(digits)
                for pos in missing_positions:
                    digit = self._read_via_neighbor_crop_ocr(pos, rects, digits)
                    if digit:
                        recovered[pos] = digit
                if len(recovered) == 6:
                    code = "".join(recovered[i] for i in range(6))
                    logger.success(
                        f"PairingCodeScreen: read code via UIA ({len(digits)}/6) + "
                        f"neighbor-crop OCR fallback for the rest: {code}"
                    )
                    return code

            time.sleep(retry_delay)

        raise RuntimeError(
            f"Could not read a complete 6-digit pairing code after {attempts} attempts "
            f"(last partial UIA read: {last_digits})"
        )

    def cancel(self) -> bool:
        if not self._cancel_button.exists(timeout=1.0):
            return False
        self._cancel_button.click()
        return True
