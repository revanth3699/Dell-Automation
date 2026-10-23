<#
.SYNOPSIS
    Checks whether file permissions survived the migration. Run on the TARGET PC AFTER
    the migration completes.

.DESCRIPTION
    Reads the SOURCE PC's seeding manifest (which captured each permission-test file's
    attributes, NTFS ACL, owner, EFS/compression state at seed time) and compares it
    against the same files as they now exist on this (Target) PC.

    The manifest records file paths relative to the DellMigrateTest marker folder, so the
    comparison works even though the two PCs have different user names / drive layouts.

    Only ACEs built from WELL-KNOWN SIDs (Everyone, Users, Administrators, ...) are
    compared, because a local-user SID differs between machines and cannot be matched.
    The seeding plan deliberately uses well-known SIDs for exactly this reason.

    You must copy the Source manifest to this PC first (the migration does not carry it,
    since testdata/output lives outside the user profile). Point -SourceManifest at it.

.PARAMETER SourceManifest
    Path to the Source PC's source_manifest_latest.json. Defaults to the local copy under
    testdata/output/ (useful for same-machine dev testing).

.PARAMETER NoJson
    Skip writing the JSON result file (console output only).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File testdata\check_permissions.ps1 -SourceManifest C:\from_source\source_manifest_latest.json

.OUTPUTS
    Console summary + testdata\output\permission_check_<timestamp>.json.
    Exit code 0 if every permission was retained, 1 otherwise.
#>
[CmdletBinding()]
param(
    [string]$SourceManifest,
    [switch]$NoJson,
    [switch]$NoHtml
)

. (Join-Path $PSScriptRoot '_common.ps1')

if (-not $SourceManifest) {
    $SourceManifest = Join-Path $PSScriptRoot 'output\source_manifest_latest.json'
}

if (-not (Test-Path -LiteralPath $SourceManifest)) {
    Write-Host "Source manifest not found: $SourceManifest" -ForegroundColor Red
    Write-Host "Copy source_manifest_latest.json from the Source PC and pass -SourceManifest." -ForegroundColor Yellow
    exit 1
}

Write-Head "Dell Migrate -- PERMISSION RETENTION CHECK"
Write-Step "source manifest: $SourceManifest"
Write-Step "this (target) machine: $env:COMPUTERNAME  user=$env:USERNAME"

$manifest = Get-Content -LiteralPath $SourceManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$permEntries = $manifest.entries | Where-Object { $_.Security }   # only those with captured security

# Normalized key for a comparable (explicit, portable) ACE.
function Ace-Key { param($a) "{0}|{1}|{2}" -f $a.Sid, $a.Rights, $a.Type }

# The ACEs the migration MUST carry across: explicit (non-inherited) + portable SID.
function Explicit-Portable { param($aces) @($aces | Where-Object { $_ -and -not $_.Inherited -and $_.Portable }) }

$results = @()
foreach ($e in $permEntries) {
    $rel = if ($e.MarkerRel) { $e.MarkerRel } else { $e.RelPath }
    $targetPath = Resolve-EntryPath $e.Category $rel

    $diffs = @()
    $status = 'RETAINED'

    $present = (Test-Path -LiteralPath $targetPath)
    if (-not $present) {
        $status = 'MISSING'
        $diffs += 'file/folder not present on target (not migrated or skipped)'
    } else {
        $t = Get-SecurityInfo $targetPath
        $s = $e.Security
        if ($null -eq $t) {
            $status = 'ERROR'; $diffs += 'could not read target security'
        } else {
            # Attribute bits that should survive (Archive deliberately ignored -- it is
            # set by the act of copying).
            foreach ($bit in 'ReadOnly','Hidden','System','Encrypted','Compressed') {
                if ([bool]$s.$bit -ne [bool]$t.$bit) {
                    $diffs += ("attribute {0}: source={1} target={2}" -f $bit, [bool]$s.$bit, [bool]$t.$bit)
                }
            }
            # Inheritance-protected flag.
            if ([bool]$s.Protected -ne [bool]$t.Protected) {
                $diffs += ("inheritance-protected: source={0} target={1}" -f [bool]$s.Protected, [bool]$t.Protected)
            }
            # Explicit, portable ACEs -- the ones that are actually checkable cross-machine.
            $srcAces = Explicit-Portable $s.Aces
            $tgtAces = Explicit-Portable $t.Aces
            $tgtKeys = @($tgtAces | ForEach-Object { Ace-Key $_ })
            foreach ($a in $srcAces) {
                if ($tgtKeys -notcontains (Ace-Key $a)) {
                    $diffs += ("missing ACE: {0} {1} {2}" -f $a.Identity, $a.Type, $a.Rights)
                }
            }
            if ($diffs.Count -gt 0 -and $status -eq 'RETAINED') { $status = 'CHANGED' }
        }
    }

    $results += [pscustomobject]@{
        RelPath  = $e.MarkerRel
        Scenario = $e.Scenario
        Note     = $e.Note
        Status   = $status
        Diffs    = $diffs
        Target   = $targetPath
    }
}

# ---- console summary ---------------------------------------------------------------
Write-Head ("Checked {0} permission-bearing files" -f $results.Count)
foreach ($r in $results) {
    $color = switch ($r.Status) { 'RETAINED' {'Green'} 'CHANGED' {'Yellow'} default {'Red'} }
    Write-Host ("  [{0,-8}] {1}" -f $r.Status, $r.RelPath) -ForegroundColor $color
    foreach ($d in $r.Diffs) { Write-Host "             - $d" -ForegroundColor $color }
}

$retained = @($results | Where-Object { $_.Status -eq 'RETAINED' }).Count
$allOk = ($retained -eq $results.Count)
Write-Head ("{0}/{1} retained" -f $retained, $results.Count)
Write-Host $(if ($allOk) { 'PASS -- all permissions retained' } else { 'FAIL -- some permissions changed or files missing' }) `
    -ForegroundColor $(if ($allOk) { 'Green' } else { 'Red' })

if (-not $NoJson) {
    $outDir = Join-Path $PSScriptRoot 'output'
    [System.IO.Directory]::CreateDirectory($outDir) | Out-Null
    $out = Join-Path $outDir ("permission_check_{0}.json" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    $payload = [pscustomobject]@{
        checkedAt    = (Get-Date).ToString('s')
        targetMachine= $env:COMPUTERNAME
        sourceManifest = $SourceManifest
        allRetained  = $allOk
        results      = $results
    }
    [System.IO.File]::WriteAllText($out, ($payload | ConvertTo-Json -Depth 8), (New-Object System.Text.UTF8Encoding($false)))
    Write-Step "JSON report: $out"
}

if (-not $NoHtml) {
    $rows = ''
    foreach ($r in $results) {
        $kind = switch ($r.Status) { 'RETAINED' { 'pass' } 'MISSING' { 'fail' } default { 'fail' } }
        $diffs = if ($r.Diffs) { (($r.Diffs | ForEach-Object { ConvertTo-HtmlText $_ }) -join '<br>') } else { '&ndash;' }
        $rows += ('<tr><td class="mono">{0}</td><td>{1}</td><td class="mono">{2}</td><td class="note">{3}</td></tr>' -f `
            (ConvertTo-HtmlText $r.RelPath), (New-Badge $r.Status $kind), (ConvertTo-HtmlText $r.Scenario), $diffs)
    }
    $body = @"
  <h2>Permission files <span class="note">($($results.Count) checked)</span></h2>
  <table>
    <tr><th>File</th><th>Status</th><th>Scenario</th><th>Differences</th></tr>
    $rows
  </table>
"@
    $changed = $results.Count - $retained
    $stats = @(
        @{ num = $results.Count; label = 'Files checked'; kind = '' },
        @{ num = $retained; label = 'Retained'; kind = 'pass' },
        @{ num = $changed; label = 'Changed/Missing'; kind = $(if ($changed) { 'fail' } else { 'pass' }) }
    )
    $sub = ("Source manifest: {0}<br>Target: {1} &middot; {2}" -f (ConvertTo-HtmlText $SourceManifest), (ConvertTo-HtmlText $env:COMPUTERNAME), (Get-Date).ToString('s'))
    $outDir = Join-Path $PSScriptRoot 'output'
    $htmlOut = Join-Path $outDir ("permission_check_{0}.html" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-HtmlReport -Title 'Permission Retention Report' -Subtitle $sub -Stats $stats `
        -Pass $retained -Fail $changed -BodyHtml $body -OverallOk $allOk -OutPath $htmlOut | Out-Null
    Write-Step "HTML report: $htmlOut"
}

exit $(if ($allOk) { 0 } else { 1 })
