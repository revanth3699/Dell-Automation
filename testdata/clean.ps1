<#
.SYNOPSIS
    Removes all Dell Migrate test data seeded by seed_source.ps1 / seed_target.ps1.

.DESCRIPTION
    Deletes the DellMigrateTest marker sub-folder from every standard user-profile
    folder (Documents, Desktop, Downloads, Pictures, Music, Videos) -- and nothing else,
    so the real contents of those folders are never touched. Also stops the background
    lock holder started by seed_source.ps1 -IncludeLocked, and clears read-only/system
    attributes first so the delete succeeds.

    Run this on BOTH PCs. Safe to run when nothing was seeded (it just reports "none").

.PARAMETER DryRun
    List what would be removed without deleting anything.

.PARAMETER Force
    Skip the confirmation prompt.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File testdata\clean.ps1
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Force
)

. (Join-Path $PSScriptRoot '_common.ps1')

Write-Head "Dell Migrate -- CLEAN test data$(if($DryRun){'  [DRY RUN]'})"

# 1) Stop the background lock holder, if any.
$sentinel = Join-Path $PSScriptRoot 'output\locked_holder.pid'
if (Test-Path -LiteralPath $sentinel) {
    $pidText = (Get-Content -LiteralPath $sentinel -Raw).Trim()
    [int]$holderPid = 0
    if ([int]::TryParse($pidText, [ref]$holderPid) -and $holderPid -gt 0) {
        Write-Step "Stopping lock holder PID $holderPid"
        if (-not $DryRun) {
            Stop-Process -Id $holderPid -Force -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $sentinel -Force -ErrorAction SilentlyContinue
        }
    }
}

# 2) Find the marker roots that actually exist.
$roots = Get-AllMarkerRoots | Where-Object { Test-Path -LiteralPath $_ }
if (-not $roots) {
    Write-OK "No DellMigrateTest folders found -- nothing to clean."
    return
}

Write-Head "Will remove:"
foreach ($r in $roots) { Write-Step $r }

if (-not $DryRun -and -not $Force) {
    $ans = Read-Host "Delete the folders listed above? (y/N)"
    if ($ans -notmatch '^(y|yes)$') { Write-Warn2 "Aborted."; return }
}

# This is a best-effort cleanup: a single native-tool stderr line (e.g. icacls on the
# >260-char path) must not abort it. _common.ps1 set ErrorActionPreference=Stop, which
# would otherwise turn a redirected native stderr line into a terminating error.
$ErrorActionPreference = 'Continue'

# An empty scratch folder we mirror onto each marker root. robocopy /MIR handles
# >260-char paths and read-only/system files natively -- plain Remove-Item does not.
$empty = Join-Path $env:TEMP ('dda_empty_' + [guid]::NewGuid().ToString('N'))
if (-not $DryRun) { [System.IO.Directory]::CreateDirectory($empty) | Out-Null }

foreach ($r in $roots) {
    if ($DryRun) { continue }
    try {
        # 0) Reset ACLs to inherited -- the perm test files carry explicit Deny ACEs and
        #    protected ACLs that can otherwise block deletion. /reset restores inheritance
        #    (removing the Deny ACEs) so the current user regains delete rights. Run via
        #    cmd so icacls's own stderr (it can't walk the >260-char path) is swallowed by
        #    cmd and never reaches PowerShell as an error.
        & cmd /c "icacls `"$r`" /reset /T /C /Q >nul 2>nul"
        # 1) Mirror the empty folder -> deletes every file/subfolder inside $r,
        #    including the deep (>260-char) tree and any read-only/system files.
        & robocopy $empty $r /MIR /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null
        # 2) Remove the now-empty root itself.
        Remove-Item -LiteralPath $r -Recurse -Force -ErrorAction SilentlyContinue
        # 3) Fallback for anything robocopy left behind.
        if (Test-Path -LiteralPath $r) {
            $lp = '\\?\' + ([System.IO.Path]::GetFullPath($r))
            Start-Process cmd -ArgumentList '/c','rmdir','/s','/q',"`"$lp`"" -NoNewWindow -Wait -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $r) {
            Write-Warn2 "Could not fully remove $r -- a file may still be locked (stop the lock holder and re-run)."
        } else {
            Write-OK "Removed $r"
        }
    } catch {
        Write-Warn2 "Could not fully remove ${r}: $($_.Exception.Message)"
    }
}

if (-not $DryRun) { Remove-Item -LiteralPath $empty -Recurse -Force -ErrorAction SilentlyContinue }

Write-Head "Done."
if ($DryRun) { Write-Warn2 "DRY RUN -- nothing was deleted." }
