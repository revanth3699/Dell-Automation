"""
Windows-native OCR (Windows.Media.Ocr via WinRT, invoked through PowerShell) -- used as a
fallback when a UI Automation read is incomplete. No extra install required; built into
Windows 10/11.

Confirmed working (2026-10-06, tools/_test_winocr.ps1): correctly read a full screenshot's
text, including a 6-digit pairing code that components/source/pairing_code_screen.py's
own UIA read couldn't fully expose (see that module's docstring for the underlying app
bug this works around).
"""

import subprocess
import tempfile
from pathlib import Path

_OCR_SCRIPT = '''param([string]$ImagePath)

Add-Type -AssemblyName System.Runtime.WindowsRuntime

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

[Windows.Media.Ocr.OcrEngine,Windows.Media.Ocr,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $engine) { Write-Output "OCR_ERROR: no OCR engine available for this Windows install"; exit 1 }

$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
Write-Output "OCR_TEXT: $($result.Text)"
'''

_script_path: "Path | None" = None


def _get_script_path() -> Path:
    global _script_path
    if _script_path is None:
        path = Path(tempfile.gettempdir()) / "dda_ocr.ps1"
        path.write_text(_OCR_SCRIPT, encoding="utf-8")
        _script_path = path
    return _script_path


def recognize_text(image_path: str, timeout: float = 15.0) -> str:
    """Returns the OCR'd text of the image at image_path. Raises RuntimeError if the OCR
    engine isn't available or the call fails."""
    script_path = _get_script_path()
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-ImagePath", image_path],
        capture_output=True, text=True, timeout=timeout,
    )
    output = result.stdout.strip()
    # Confirmed live (2026-10-06): when OCR recognizes NO text at all (e.g. a crop too
    # small/blank for the engine), the PowerShell script's own trailing space after the
    # colon gets eaten by this strip() call, turning "OCR_TEXT: " into "OCR_TEXT:" --
    # matching with a bare prefix (no required trailing space) handles that case too,
    # correctly returning an empty string instead of spuriously raising.
    if output.startswith("OCR_TEXT:"):
        return output[len("OCR_TEXT:"):].lstrip(" ")
    raise RuntimeError(f"OCR failed: {output or result.stderr.strip()}")
