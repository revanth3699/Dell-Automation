<#
.SYNOPSIS
    Seeds the TARGET (new) PC with pre-existing data that collides with the Source PC's
    migration test data for the Dell Data Assistant.

.DESCRIPTION
    Writes the Target side of the shared plan in _common.ps1 into the standard
    user-profile folders, all under a single DellMigrateTest marker sub-folder. Run this
    on the Target PC BEFORE pairing, with the SAME -Profile you pass to seed_source.ps1
    on the Source PC, so the collisions line up on identical relative paths.

    What ends up on the Target before migration:
      - conflict  : same name + path as a Source file, but DIFFERENT content
                    (content is marked "TARGET" so you can see which side wins).
      - identical : same name + path as a Source file, byte-for-byte EQUAL content.
      - same-folder: a folder the Source also has, containing DIFFERENT filenames
                     (plus one nested same-name/different-content file).
      - target-only: data that exists ONLY on the Target and must survive the migration.

    The Target has none of the Source-only / edge / stress cases -- those are what the
    Source sends across.

.PARAMETER Profile
    Minimal | Standard | Stress -- must match the Source run (kept for symmetry; the
    Target side has no volume-driven cases, so it mainly affects the manifest label).

.PARAMETER DryRun
    List what would be created without writing anything.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File testdata\seed_target.ps1 -Profile Standard
#>
[CmdletBinding()]
param(
    [ValidateSet('Minimal','Standard','Stress')][string]$Profile = 'Standard',
    [switch]$DryRun
)

. (Join-Path $PSScriptRoot '_common.ps1')
$script:IsDryRun = [bool]$DryRun

Write-Head "Dell Migrate -- SEED TARGET PC  (profile: $Profile$(if($DryRun){' [DRY RUN]'}))"
Write-Step "user=$env:USERNAME  machine=$env:COMPUTERNAME"

$plan = Get-TestDataPlan -Profile $Profile

$written = 0
foreach ($class in ($plan | Select-Object -ExpandProperty Class -Unique)) {
    $entries = $plan | Where-Object { $_.Class -eq $class -and $null -ne $_.Target }
    if (-not $entries) { continue }
    Write-Head "[$class]"
    foreach ($e in $entries) {
        Write-Step ("{0,-10} {1}" -f $e.Category, $e.RelPath)
        if (Invoke-SeedEntry -Entry $e -Side 'Target') { $written++ }
    }
}

Write-Head "Done."
Write-OK ("Target seeding complete: {0} plan entries written." -f $written)
if (-not $DryRun) {
    $m = Save-Manifest -Role 'target'
    Write-Step "Manifest: $m"
    Write-Step "These files must still exist (target-only) or be merged (same-folder) after migration."
} else {
    Write-Warn2 "DRY RUN -- nothing was written."
}
