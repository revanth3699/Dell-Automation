<#
.SYNOPSIS
    Seeds the SOURCE (old) PC with migration test data for the Dell Data Assistant.

.DESCRIPTION
    Writes a deterministic test dataset into the standard user-profile folders
    (Documents, Desktop, Downloads, Pictures, Music, Videos), all under a single
    DellMigrateTest marker sub-folder so clean.ps1 can remove it safely.

    The dataset is the Source side of the shared plan in _common.ps1. Run
    seed_target.ps1 on the Target PC with the SAME -Profile so the conflict / identical
    / same-folder cases line up on identical relative paths across the two machines.

    Covers: clean source-only copies; name collisions with different content; identical
    (byte-equal) files; same-folder merges; and source-only edge cases -- empty folder,
    zero-byte file, >260-char path, ~200-char filename, accented/emoji/special-char
    names, hidden/read-only/system attributes, archive + executable types, a configurable
    flood of tiny files, a configurable large file, and (optionally) a locked in-use file.

.PARAMETER Profile
    Minimal | Standard | Stress -- controls the many-small count and large-file size.
    Minimal: 20 tiny files, no big file.  Standard: 200 + 256 MB.  Stress: 5000 + 2 GB.

.PARAMETER ManySmallCount
    Override the many-small file count.

.PARAMETER BigFileMB
    Override the large-file size in MB (0 = no large file).

.PARAMETER IncludeLocked
    Also create a file and hold an exclusive handle on it (background process) so the
    migration hits a genuinely in-use/locked file. clean.ps1 releases it.

.PARAMETER LockMinutes
    How long the locked-file handle is held (default 30).

.PARAMETER DryRun
    List what would be created without writing anything.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File testdata\seed_source.ps1 -Profile Standard

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File testdata\seed_source.ps1 -Profile Stress -IncludeLocked
#>
[CmdletBinding()]
param(
    [ValidateSet('Minimal','Standard','Stress')][string]$Profile = 'Standard',
    [int]$ManySmallCount = 0,
    [double]$BigFileMB   = 0,
    [switch]$IncludeLocked,
    [int]$LockMinutes    = 30,
    [switch]$DryRun
)

. (Join-Path $PSScriptRoot '_common.ps1')
$script:IsDryRun = [bool]$DryRun

Write-Head "Dell Migrate -- SEED SOURCE PC  (profile: $Profile$(if($DryRun){' [DRY RUN]'}))"
Write-Step "user=$env:USERNAME  machine=$env:COMPUTERNAME"

$plan = Get-TestDataPlan -Profile $Profile -ManySmallCount $ManySmallCount -BigFileMB $BigFileMB

# Rough disk-space guard for the large file.
$big = $plan | Where-Object { $_.Kind -eq 'big' } | Select-Object -First 1
if ($big -and -not $DryRun) {
    $drive = (Get-Item (Get-KnownFolder 'Videos')).PSDrive
    $free  = (Get-PSDrive $drive.Name).Free
    if ($free -lt ($big.Size * 1.1)) {
        Write-Warn2 ("Large file wants {0:N0} MB but only {1:N0} MB free on {2}: -- skipping it." -f ($big.Size/1MB), ($free/1MB), $drive.Name)
        $plan = $plan | Where-Object { $_.Kind -ne 'big' }
    }
}

$written = 0
foreach ($class in ($plan | Select-Object -ExpandProperty Class -Unique)) {
    $entries = $plan | Where-Object { $_.Class -eq $class -and $null -ne $_.Source }
    if (-not $entries) { continue }
    Write-Head "[$class]"
    foreach ($e in $entries) {
        $path = Resolve-EntryPath $e.Category $e.RelPath
        Write-Step ("{0,-10} {1}" -f $e.Category, $e.RelPath)
        if (Invoke-SeedEntry -Entry $e -Side 'Source') { $written++ }
    }
}

# ---- optional locked / in-use file -------------------------------------------------
if ($IncludeLocked) {
    Write-Head "[edge-locked]"
    $lockPath = Resolve-EntryPath 'Documents' 'edge\locked\inuse.txt'
    Write-Step "Documents  edge\locked\inuse.txt  (held open for $LockMinutes min)"
    if (-not $DryRun) {
        Write-TextFile -Path $lockPath -Content "This file is held open by a background process."
        Add-ManifestEntry -Class 'edge-locked' -Category 'Documents' -RelPath 'edge\locked\inuse.txt' `
            -FullPath $lockPath -Kind 'text' -Side 'Source' -Attr @() -Note 'held exclusively open'
        $sec = $LockMinutes * 60
        $holder = @"
`$fs = [System.IO.File]::Open('$lockPath', [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
Start-Sleep -Seconds $sec
`$fs.Close()
"@
        $proc = Start-Process powershell -PassThru -WindowStyle Hidden `
            -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-Command',$holder
        $sentinel = Join-Path $PSScriptRoot 'output\locked_holder.pid'
        [System.IO.Directory]::CreateDirectory((Split-Path $sentinel)) | Out-Null
        [System.IO.File]::WriteAllText($sentinel, $proc.Id.ToString(), $script:Utf8NoBom)
        Write-Warn2 "Lock holder PID $($proc.Id) -- clean.ps1 will stop it (or kill it manually)."
    }
}

Write-Head "Done."
Write-OK ("Source seeding complete: {0} plan entries written." -f $written)
if (-not $DryRun) {
    $m = Save-Manifest -Role 'source'
    Write-Step "Manifest: $m"
    Write-Step "Marker folders seeded under: Documents, Desktop, Downloads, Pictures, Music, Videos"
} else {
    Write-Warn2 "DRY RUN -- nothing was written."
}
