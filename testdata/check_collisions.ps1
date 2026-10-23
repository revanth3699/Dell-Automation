<#
.SYNOPSIS
    Validates every seeded case against the live files on the TARGET PC after a migration
    -- collisions AND edge cases. Run on the Target, after the migration, before cleanup.

.DESCRIPTION
    This is an on-disk check, independent of the Dell migration-report PDF
    (validate_migration.py covers what the report CLAIMS; this covers what actually
    happened to each seeded file). It compares the Source and Target seed manifests to the
    live files on this PC and reports, per case:

      collisions (present on both PCs):
        - identical (same content)  -> must still exist and be intact.
        - conflict  (different content) -> which side won (SOURCE / TARGET / OTHER / MISSING).
      preservation (Target-only, incl. same-folder from_target_*):
        - must NOT be deleted or changed by the migration.
      migration (Source-only, incl. same-folder from_source_* and ALL edge cases):
        - reported as migrated / changed / not-migrated. Edge cases covered: empty folder,
          zero-byte, >260-char path, long name, special-char names, hidden/readonly/system,
          zip/exe, many-small folder, and the large file (compared by size).

    HARD FAILURES (exit 1) are only unambiguous data loss / corruption: a Target-only or
    pre-existing same-folder file LOST or CHANGED, an identical file LOST or CORRUPT, a
    conflict file that VANISHED, and -- when -ExpectedConflictWinner is set -- a conflict
    whose winner differs. Everything else (conflict winners, whether Source/edge files
    migrated) is REPORTED, because Dell may legitimately skip some files (e.g. .exe, a
    locked file) and its conflict-resolution policy is not assumed here. Use
    -RequireMigrated to turn "not migrated" into a failure for the plain Source-only files.

.PARAMETER SourceManifest   Source PC's source_manifest_latest.json (copied/fetched here).
.PARAMETER TargetManifest   This PC's target_manifest_latest.json (default: local output copy).
.PARAMETER ExpectedConflictWinner  '' | 'source' | 'target' -- assert the conflict winner.
.PARAMETER RequireMigrated  Fail if a plain source-only file did not migrate in.
.PARAMETER NoJson           Console only.

.OUTPUTS
    Console summary + testdata\output\collision_check_<timestamp>.json. Exit 0 if no
    failures, 1 otherwise.
#>
[CmdletBinding()]
param(
    [string]$SourceManifest,
    [string]$TargetManifest,
    [ValidateSet('', 'source', 'target')][string]$ExpectedConflictWinner = '',
    [switch]$RequireMigrated,
    [switch]$NoJson
)

. (Join-Path $PSScriptRoot '_common.ps1')

if (-not $SourceManifest) { $SourceManifest = Join-Path $PSScriptRoot 'output\source_manifest_latest.json' }
if (-not $TargetManifest) { $TargetManifest = Join-Path $PSScriptRoot 'output\target_manifest_latest.json' }
foreach ($m in @($SourceManifest, $TargetManifest)) {
    if (-not (Test-Path -LiteralPath $m)) {
        Write-Host "Manifest not found: $m" -ForegroundColor Red
        exit 1
    }
}

# edge-perms is validated separately by check_permissions.ps1; everything else is here.
# -Encoding UTF8 matters: the manifests are UTF-8 and contain unicode filenames (accents,
# emoji); PS 5.1's Get-Content defaults to ANSI and would mangle them into path mismatches.
$src = (Get-Content -LiteralPath $SourceManifest -Raw -Encoding UTF8 | ConvertFrom-Json).entries |
    Where-Object { $_.Class -ne 'edge-perms' -and $_.MarkerRel }
$tgt = (Get-Content -LiteralPath $TargetManifest -Raw -Encoding UTF8 | ConvertFrom-Json).entries |
    Where-Object { $_.Class -ne 'edge-perms' -and $_.MarkerRel }

$srcByRel = @{}; foreach ($e in $src) { $srcByRel[$e.MarkerRel] = $e }
$tgtByRel = @{}; foreach ($e in $tgt) { $tgtByRel[$e.MarkerRel] = $e }

function Is-Folder { param($e) $e.Kind -in @('empty', 'manysmall') }

function Live-Exists { param($Path, [bool]$Folder)
    $lp = To-LongPath $Path
    if ($Folder) { return [System.IO.Directory]::Exists($lp) }
    return [System.IO.File]::Exists($lp)
}
function Live-Size { param($Path) ([System.IO.FileInfo](To-LongPath $Path)).Length }
function Live-Hash { param($Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $fs = [System.IO.File]::OpenRead((To-LongPath $Path))
    try { return ([BitConverter]::ToString($sha.ComputeHash($fs))).Replace('-', '') }
    finally { $fs.Dispose(); $sha.Dispose() }
}

# Compares a live file/folder to a manifest entry. Returns a status string; for files it
# prefers hash, falls back to size (large files), then to existence (long-path entries
# whose hash/size could not be captured at seed time).
function Compare-To-Entry { param($Entry, $OkStatus, $MissingStatus, $ChangedStatus)
    $path = Resolve-EntryPath $Entry.Category $Entry.MarkerRel
    $folder = Is-Folder $Entry
    if (-not (Live-Exists $path $folder)) { return $MissingStatus }
    if ($folder) { return $OkStatus }
    if ($Entry.Sha256) {
        if ((Live-Hash $path) -eq $Entry.Sha256) { return $OkStatus }
        return $ChangedStatus
    }
    if ($null -ne $Entry.Size) {
        if ((Live-Size $path) -eq $Entry.Size) { return $OkStatus }
        return $ChangedStatus
    }
    return $OkStatus   # present, but nothing recorded to compare (e.g. long-path entry)
}

$results = @()
$handled = @{}

# --- 1) present on BOTH PCs: identical integrity, or conflict winner ------------------
foreach ($rel in $srcByRel.Keys) {
    if (-not $tgtByRel.ContainsKey($rel)) { continue }
    $s = $srcByRel[$rel]; $t = $tgtByRel[$rel]; $handled[$rel] = $true
    $path = Resolve-EntryPath $t.Category $rel
    $exists = Live-Exists $path $false
    $live = if ($exists) { Live-Hash $path } else { $null }
    if ($s.Sha256 -eq $t.Sha256) {
        if (-not $exists)            { $status = 'IDENTICAL-LOST';    $fail = $true }
        elseif ($live -eq $s.Sha256) { $status = 'IDENTICAL-OK';      $fail = $false }
        else                         { $status = 'IDENTICAL-CORRUPT'; $fail = $true }
        $results += [pscustomobject]@{ Class=$s.Class; Rel=$rel; Status=$status; Winner=$null; Fail=$fail }
    } else {
        if     (-not $exists)        { $winner = 'missing' }
        elseif ($live -eq $s.Sha256) { $winner = 'source' }
        elseif ($live -eq $t.Sha256) { $winner = 'target' }
        else                         { $winner = 'other' }
        $fail = ($winner -eq 'missing') -or ($ExpectedConflictWinner -and $winner -ne $ExpectedConflictWinner)
        $results += [pscustomobject]@{ Class=$s.Class; Rel=$rel; Status="CONFLICT-$($winner.ToUpper())"; Winner=$winner; Fail=$fail }
    }
}

# --- 2) Target-only (incl. same-folder from_target_*): must NOT be lost/changed -------
foreach ($rel in $tgtByRel.Keys) {
    if ($handled.ContainsKey($rel)) { continue }
    $t = $tgtByRel[$rel]
    $status = Compare-To-Entry $t 'TARGET-RETAINED' 'TARGET-LOST' 'TARGET-CHANGED'
    $results += [pscustomobject]@{ Class=$t.Class; Rel=$rel; Status=$status; Winner=$null
        Fail = ($status -in @('TARGET-LOST', 'TARGET-CHANGED')) }
}

# --- 3) Source-only + ALL edge cases: did they migrate in? (reported) -----------------
foreach ($rel in $srcByRel.Keys) {
    if ($handled.ContainsKey($rel)) { continue }
    $s = $srcByRel[$rel]
    $folder = Is-Folder $s
    $okStatus = if ($folder) { 'FOLDER-MIGRATED' } else { 'MIGRATED-OK' }
    $status = Compare-To-Entry $s $okStatus 'NOT-MIGRATED' 'MIGRATED-CHANGED'
    # Plain source-only files are the ones expected to always migrate; edge cases may be
    # skipped by policy, so only source-only drives a failure under -RequireMigrated.
    $fail = $RequireMigrated -and $s.Class -eq 'source-only' -and $status -eq 'NOT-MIGRATED'
    $results += [pscustomobject]@{ Class=$s.Class; Rel=$rel; Status=$status; Winner=$null; Fail=$fail }
}

# ---- console summary ---------------------------------------------------------------
Write-Head ("Collision + edge-case check -- {0} cases" -f $results.Count)
foreach ($r in ($results | Sort-Object Class, Rel)) {
    $color = if ($r.Fail) { 'Red' }
             elseif ($r.Status -like 'CONFLICT-*' -or $r.Status -like 'NOT-*' -or $r.Status -like '*CHANGED') { 'Yellow' }
             else { 'Green' }
    Write-Host ("  [{0,-16}] {1,-14} {2}" -f $r.Status, $r.Class, $r.Rel) -ForegroundColor $color
}

$failed = @($results | Where-Object { $_.Fail })
$conflicts = @($results | Where-Object { $_.Status -like 'CONFLICT-*' })
$allOk = ($failed.Count -eq 0)
Write-Head ("{0} failures (data loss / corruption); {1} conflicts resolved" -f $failed.Count, $conflicts.Count)
foreach ($c in $conflicts) { Write-Step ("conflict {0} -> {1}" -f $c.Rel, $c.Winner) }
Write-Host $(if ($allOk) { 'PASS -- no data loss or corruption' } else { 'FAIL -- see red rows above' }) `
    -ForegroundColor $(if ($allOk) { 'Green' } else { 'Red' })

if (-not $NoJson) {
    $outDir = Join-Path $PSScriptRoot 'output'
    [System.IO.Directory]::CreateDirectory($outDir) | Out-Null
    $out = Join-Path $outDir ("collision_check_{0}.json" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    $payload = [pscustomobject]@{
        checkedAt = (Get-Date).ToString('s'); targetMachine = $env:COMPUTERNAME
        expectedConflictWinner = $ExpectedConflictWinner; requireMigrated = [bool]$RequireMigrated
        allOk = $allOk; results = $results
    }
    [System.IO.File]::WriteAllText($out, ($payload | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))
    Write-Step "JSON report: $out"
}

exit $(if ($allOk) { 0 } else { 1 })
