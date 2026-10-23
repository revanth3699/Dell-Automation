# _common.ps1 -- shared library for the Dell Migrate test-data seeding scripts.
#
# Dot-sourced by seed_source.ps1, seed_target.ps1 and clean.ps1. It holds the ONE
# shared data plan (Get-TestDataPlan) so the Source PC and the Target PC seed the
# EXACT same relative paths -- that is what makes "same folder / same filename,
# different content" an actual collision the Dell Data Assistant has to resolve.
#
# Everything is written under a single marker sub-folder (DellMigrateTest) inside each
# standard user-profile folder, so clean.ps1 can remove all of it without ever touching
# the real contents of Documents/Desktop/Pictures/etc.
#
# PowerShell 5.1 compatible. All source text is ASCII; any non-ASCII filename (accents,
# emoji) is built at runtime from code points so this file never needs a BOM.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:MarkerFolderName = 'DellMigrateTest'
$script:Utf8NoBom        = New-Object System.Text.UTF8Encoding($false)
$script:Manifest         = New-Object System.Collections.Generic.List[object]
$script:IsDryRun           = $false

# --------------------------------------------------------------------- logging

function Write-Step  { param([string]$m) Write-Host "  - $m" }
function Write-Head  { param([string]$m) Write-Host ""; Write-Host $m -ForegroundColor Cyan }
function Write-Warn2 { param([string]$m) Write-Host "  ! $m" -ForegroundColor Yellow }
function Write-OK    { param([string]$m) Write-Host $m -ForegroundColor Green }

# --------------------------------------------------------------------- known folders

function Get-KnownFolder {
    param([Parameter(Mandatory)][string]$Key)
    switch ($Key) {
        'Documents' { return [Environment]::GetFolderPath('MyDocuments') }
        'Desktop'   { return [Environment]::GetFolderPath('DesktopDirectory') }
        'Pictures'  { return [Environment]::GetFolderPath('MyPictures') }
        'Music'     { return [Environment]::GetFolderPath('MyMusic') }
        'Videos'    { return [Environment]::GetFolderPath('MyVideos') }
        'Downloads' {
            $d = Join-Path $HOME 'Downloads'
            return $d
        }
        default { throw "Unknown known-folder key: $Key" }
    }
}

# Absolute path of a plan entry: <KnownFolder>\DellMigrateTest\<RelPath>
function Resolve-EntryPath {
    param([string]$Category, [string]$RelPath)
    $root = Join-Path (Get-KnownFolder $Category) $script:MarkerFolderName
    if ([string]::IsNullOrEmpty($RelPath)) { return $root }
    return (Join-Path $root $RelPath)
}

# Marker roots across every category -- used by clean.ps1.
function Get-AllMarkerRoots {
    $keys = 'Documents','Desktop','Pictures','Music','Videos','Downloads'
    $out = @()
    foreach ($k in $keys) {
        $out += (Join-Path (Get-KnownFolder $k) $script:MarkerFolderName)
    }
    return $out
}

# --------------------------------------------------------------------- byte helpers

function Convert-HexToBytes {
    param([string]$Hex)
    if ([string]::IsNullOrEmpty($Hex)) { return New-Object byte[] 0 }
    $Hex = ($Hex -replace '\s', '')
    $bytes = New-Object byte[] ($Hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($Hex.Substring($i * 2, 2), 16)
    }
    return ,$bytes
}

# Deterministic 32-bit seed from a string -- identical across both machines, so a file
# built from the same seed on Source and Target comes out byte-for-byte identical.
function Get-IntSeed {
    param([string]$Text)
    $md5 = [System.Security.Cryptography.MD5]::Create()
    try {
        $h = $md5.ComputeHash($script:Utf8NoBom.GetBytes($Text))
        return [BitConverter]::ToInt32($h, 0)
    } finally { $md5.Dispose() }
}

# The "long path" prefix lets .NET create/write paths past the legacy 260-char limit
# even on systems where long-path support is not enabled.
function To-LongPath {
    param([string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    if ($full.StartsWith('\\?\')) { return $full }
    if ($full.StartsWith('\\'))   { return '\\?\UNC\' + $full.Substring(2) }
    return '\\?\' + $full
}

# --------------------------------------------------------------------- writers

function New-Dir {
    param([string]$Path, [switch]$Long)
    if ($script:IsDryRun) { return }
    $p = if ($Long) { To-LongPath $Path } else { $Path }
    [System.IO.Directory]::CreateDirectory($p) | Out-Null
}

function Write-TextFile {
    param([string]$Path, [string]$Content, [switch]$Long)
    if ($script:IsDryRun) { return }
    $p = if ($Long) { To-LongPath $Path } else { $Path }
    $dir = [System.IO.Path]::GetDirectoryName($p)
    [System.IO.Directory]::CreateDirectory($dir) | Out-Null
    [System.IO.File]::WriteAllText($p, $Content, $script:Utf8NoBom)
}

function Write-BinFile {
    param(
        [string]$Path,
        [string]$Seed,
        [long]$Size,
        [string]$HeaderHex = '',
        [switch]$Long
    )
    if ($script:IsDryRun) { return }
    $p = if ($Long) { To-LongPath $Path } else { $Path }
    $dir = [System.IO.Path]::GetDirectoryName($p)
    [System.IO.Directory]::CreateDirectory($dir) | Out-Null

    $header   = Convert-HexToBytes $HeaderHex
    $bodyLen  = [Math]::Max([long]0, $Size - $header.Length)
    $rnd      = New-Object System.Random((Get-IntSeed $Seed))
    $fs       = [System.IO.File]::Open($p, [System.IO.FileMode]::Create)
    try {
        if ($header.Length -gt 0) { $fs.Write($header, 0, $header.Length) }
        if ($bodyLen -le 4MB) {
            # Small file: one deterministic buffer.
            $buf = New-Object byte[] $bodyLen
            $rnd.NextBytes($buf)
            $fs.Write($buf, 0, $buf.Length)
        } else {
            # Large file: fill one 1 MB buffer and repeat it (fast; source-only, so
            # byte-identicality across machines is not required here).
            $chunk = New-Object byte[] (1MB)
            $rnd.NextBytes($chunk)
            $remaining = $bodyLen
            while ($remaining -gt 0) {
                $n = [Math]::Min([long]$chunk.Length, $remaining)
                $fs.Write($chunk, 0, $n)
                $remaining -= $n
            }
        }
    } finally { $fs.Dispose() }
}

function Set-FileAttrs {
    param([string]$Path, [string[]]$Attrs)
    if ($script:IsDryRun -or -not $Attrs) { return }
    $value = [System.IO.FileAttributes]::Normal
    foreach ($a in $Attrs) { $value = $value -bor ([System.IO.FileAttributes]$a) }
    # Drop Normal if any real attribute was OR-ed in.
    if ($value -ne [System.IO.FileAttributes]::Normal) {
        $value = $value -band (-bnot [System.IO.FileAttributes]::Normal)
    }
    [System.IO.File]::SetAttributes($Path, $value)
}

# --------------------------------------------------------------------- manifest

function Add-ManifestEntry {
    param(
        [string]$Class, [string]$Category, [string]$RelPath, [string]$FullPath,
        [string]$Kind, [string]$Side, [string[]]$Attr, [string]$Note
    )
    $size = $null; $hash = $null
    if (-not $script:IsDryRun) {
        try {
            if ([System.IO.File]::Exists($FullPath)) {
                $size = (Get-Item -LiteralPath $FullPath -Force).Length
                $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $FullPath).Hash
            }
        } catch { }   # hashing a locked/odd file is best-effort only
    }
    $script:Manifest.Add([pscustomobject]@{
        Class    = $Class
        Category = $Category
        RelPath  = $RelPath
        FullPath = $FullPath
        Kind     = $Kind
        Side     = $Side
        Attr     = ($Attr -join ',')
        Size     = $size
        Sha256   = $hash
        Note     = $Note
    })
}

function Save-Manifest {
    param([string]$Role)
    $outDir = Join-Path $PSScriptRoot 'output'
    [System.IO.Directory]::CreateDirectory($outDir) | Out-Null
    $stamp   = Get-Date -Format 'yyyyMMdd-HHmmss'
    $stamped = Join-Path $outDir ("{0}_manifest_{1}.json" -f $Role, $stamp)
    $latest  = Join-Path $outDir ("{0}_manifest_latest.json" -f $Role)
    $payload = [pscustomobject]@{
        role        = $Role
        machine     = $env:COMPUTERNAME
        user        = $env:USERNAME
        generatedAt = (Get-Date).ToString('s')
        dryRun      = [bool]$script:IsDryRun
        markerName  = $script:MarkerFolderName
        entries     = $script:Manifest
    }
    $json = $payload | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($stamped, $json, $script:Utf8NoBom)
    [System.IO.File]::WriteAllText($latest,  $json, $script:Utf8NoBom)
    return $latest
}

# --------------------------------------------------------------------- the data plan

# File-format magic bytes so each generated binary at least starts like its extension
# (enough for category detection; these are TEST files, not valid playable media).
$script:Magic = @{
    pdf  = '25504446'                     # %PDF
    png  = '89504E470D0A1A0A'
    jpg  = 'FFD8FFE0'
    mp3  = '494433'                       # ID3
    mp4  = '0000001C66747970697336340000'  # ...ftyp
    zip  = '504B0304'
    exe  = '4D5A'                         # MZ
    bin  = ''
}

# Build the non-ASCII sample filenames from code points (keeps this file BOM-free).
function Get-SpecialNames {
    $eacute = [char]0x00E9                     # e-acute
    $emoji  = [System.Char]::ConvertFromUtf32(0x1F600)  # grinning face
    return @(
        ('r{0}sum{0} caf{0}.txt' -f $eacute),  # accents
        'report (final) [v2].txt',             # brackets, parentheses, spaces
        'a & b ; c = d.txt',                    # shell-special characters
        ('note {0} here.txt' -f $emoji)         # emoji / astral plane
    )
}

# Returns the full list of plan entries. Each entry describes ONE logical file (or
# folder) and both machines' content for it:
#   Class    taxonomy bucket (drives what the entry is testing)
#   Category known-folder key it lives under
#   RelPath  path under <Category>\DellMigrateTest\
#   Kind     text | bin | zero | empty | big | manysmall | longpath | longname | special
#   Source   content (text) / seed (bin) for the Source PC, or $null if Source has none
#   Target   same, for the Target PC, or $null if Target has none
#   Size     bytes for bin/big
#   Header   magic-hex key into $script:Magic for bin/big
#   Attr     file attributes to apply (Hidden/ReadOnly/System)
#   Count    file count for manysmall
#   Note     human description
#
# IDENTICAL content == Source and Target carry the same string (same text, or same bin
# seed+size+header) so the two files come out byte-for-byte equal.
function Get-TestDataPlan {
    param(
        [ValidateSet('Minimal','Standard','Stress')][string]$Profile = 'Standard',
        [int]$ManySmallCount = 0,
        [double]$BigFileMB   = 0
    )

    # Profile-driven volume knobs (explicit params win over the profile default).
    switch ($Profile) {
        'Minimal'  { $manyDefault = 20;   $bigDefaultMB = 0 }
        'Standard' { $manyDefault = 200;  $bigDefaultMB = 256 }
        'Stress'   { $manyDefault = 5000; $bigDefaultMB = 2048 }
    }
    if ($ManySmallCount -gt 0) { $manyDefault  = $ManySmallCount }
    if ($BigFileMB      -gt 0) { $bigDefaultMB = $BigFileMB }

    $P = New-Object System.Collections.Generic.List[object]
    function Add-Entry {
        param($Class,$Category,$RelPath,$Kind,$Source,$Target,
              [long]$Size=0,$Header='',[string[]]$Attr=@(),[int]$Count=0,$Note='')
        $P.Add([pscustomobject]@{
            Class=$Class; Category=$Category; RelPath=$RelPath; Kind=$Kind;
            Source=$Source; Target=$Target; Size=$Size; Header=$Header;
            Attr=$Attr; Count=$Count; Note=$Note
        })
    }

    # ---- A. Source-only clean transfers (should land on Target untouched) ----------
    Add-Entry 'source-only' 'Documents' 'source-only\notes.txt'       'text' "Meeting notes - source PC`nAction items: migrate everything." $null -Note 'plain text should copy cleanly'
    Add-Entry 'source-only' 'Documents' 'source-only\report.pdf'      'bin'  'src-report' $null -Size 65536  -Header 'pdf' -Note 'document-category binary'
    Add-Entry 'source-only' 'Documents' 'source-only\budget.xlsx'     'bin'  'src-xlsx'   $null -Size 32768  -Header 'zip' -Note 'xlsx is a zip container'
    Add-Entry 'source-only' 'Pictures'  'source-only\vacation.jpg'    'bin'  'src-jpg'    $null -Size 196608 -Header 'jpg' -Note 'picture category'
    Add-Entry 'source-only' 'Pictures'  'source-only\diagram.png'     'bin'  'src-png'    $null -Size 49152  -Header 'png'
    Add-Entry 'source-only' 'Music'     'source-only\song.mp3'        'bin'  'src-mp3'    $null -Size 131072 -Header 'mp3' -Note 'music category'
    Add-Entry 'source-only' 'Videos'    'source-only\clip.mp4'        'bin'  'src-mp4'    $null -Size 524288 -Header 'mp4' -Note 'video category'
    Add-Entry 'source-only' 'Desktop'   'source-only\todo.txt'        'text' "Desktop TODO on the old PC." $null
    Add-Entry 'source-only' 'Downloads' 'source-only\notes-dl.txt'    'text' "A file sitting in Downloads." $null

    # ---- B. Conflict: SAME relpath on both PCs, DIFFERENT content -------------------
    Add-Entry 'conflict-diff' 'Documents' 'conflict\budget.csv'  'text' "owner,amount`nSOURCE,1000" "owner,amount`nTARGET,9999" -Note 'same name, different text -- which wins?'
    Add-Entry 'conflict-diff' 'Documents' 'conflict\readme.txt'  'text' "This README came from the SOURCE (old) PC." "This README was ALREADY on the TARGET (new) PC." -Note 'content marker tells you which survived'
    Add-Entry 'conflict-diff' 'Pictures'  'conflict\profile.png' 'bin'  'src-profile' 'tgt-profile' -Size 49152 -Header 'png' -Note 'same name+size, different bytes'

    # ---- C. Identical: SAME relpath, byte-for-byte SAME content ---------------------
    Add-Entry 'identical' 'Documents' 'identical\license.txt' 'text' "MIT License - identical on both PCs." "MIT License - identical on both PCs." -Note 'de-dup / skip-identical behavior'
    Add-Entry 'identical' 'Pictures'  'identical\logo.png'    'bin'  'shared-logo' 'shared-logo' -Size 16384 -Header 'png' -Note 'identical image'
    Add-Entry 'identical' 'Music'     'identical\jingle.mp3'  'bin'  'shared-jingle' 'shared-jingle' -Size 32768 -Header 'mp3'

    # ---- D. Same folder name on both PCs, DIFFERENT files inside (merge) ------------
    Add-Entry 'same-folder' 'Documents' 'shared-folder\from_source_1.txt' 'text' "Only on source, inside the shared folder." $null -Note 'expect union of both PCs files'
    Add-Entry 'same-folder' 'Documents' 'shared-folder\from_source_2.txt' 'text' "Second source-only file in the shared folder." $null
    Add-Entry 'same-folder' 'Documents' 'shared-folder\from_target_1.txt' 'text' $null "Only on target, inside the shared folder." -Note 'target side of the merge'
    Add-Entry 'same-folder' 'Documents' 'shared-folder\from_target_2.txt' 'text' $null "Second target-only file in the shared folder."
    # A file present in BOTH the shared folder with different content (nested conflict).
    Add-Entry 'same-folder' 'Documents' 'shared-folder\shared_note.txt'   'text' "shared_note from SOURCE" "shared_note from TARGET" -Note 'conflict nested inside the merged folder'

    # ---- E. Target-only (pre-existing data that must NOT be deleted) ----------------
    Add-Entry 'target-only' 'Documents' 'target-only\tax_2024.pdf'      'bin'  $null 'tgt-tax' -Size 40960 -Header 'pdf' -Note 'must still exist after migration'
    Add-Entry 'target-only' 'Pictures'  'target-only\old_wallpaper.jpg' 'bin'  $null 'tgt-wall' -Size 65536 -Header 'jpg'

    # ---- F. Source-only edge / stress cases (exercise skip + capacity paths) --------
    Add-Entry 'edge-empty'     'Documents' 'edge\empty-folder'          'empty' 'x' $null -Note 'empty directory -- nothing to copy'
    Add-Entry 'edge-zero'      'Documents' 'edge\zero-byte.dat'         'zero'  'x' $null -Note '0-byte file'
    Add-Entry 'edge-longpath'  'Documents' 'edge\deep'                  'longpath' 'x' $null -Note 'path well past 260 chars'
    Add-Entry 'edge-longname'  'Documents' 'edge\longname'              'longname' 'x' $null -Note '~200-char filename'
    Add-Entry 'edge-special'   'Documents' 'edge\special'               'special'  'x' $null -Note 'accents, emoji, brackets, & ; ='
    Add-Entry 'edge-hidden'    'Documents' 'edge\attrs\hidden.txt'      'text' "hidden file" $null -Attr @('Hidden') -Note 'hidden attribute'
    Add-Entry 'edge-readonly'  'Documents' 'edge\attrs\readonly.txt'    'text' "read-only file" $null -Attr @('ReadOnly') -Note 'read-only attribute'
    Add-Entry 'edge-system'    'Documents' 'edge\attrs\system.txt'      'text' "system file" $null -Attr @('System','Hidden') -Note 'system+hidden'
    Add-Entry 'edge-ext-zip'   'Downloads' 'edge\archive.zip'           'bin'  'src-zip' $null -Size 65536 -Header 'zip' -Note 'archive type'
    Add-Entry 'edge-ext-exe'   'Downloads' 'edge\tool.exe'              'bin'  'src-exe' $null -Size 65536 -Header 'exe' -Note 'executable -- may be skipped by policy'
    Add-Entry 'edge-manysmall' 'Downloads' 'edge\many-small'           'manysmall' 'x' $null -Count $manyDefault -Note 'many tiny files -> progress/counting'
    if ($bigDefaultMB -gt 0) {
        Add-Entry 'edge-large' 'Videos' 'edge\bigfile.bin' 'big' 'src-big' $null -Size ([long]$bigDefaultMB * 1MB) -Header 'bin' -Note 'large file -> capacity / does-not-fit'
    }
    # Locked / in-use file is created only with -IncludeLocked (see seed_source.ps1).

    return $P
}

# --------------------------------------------------------------------- materializer

# Writes ONE side of a plan entry to disk and records it in the manifest. $Side is
# 'Source' or 'Target'; the matching content field ($entry.Source / $entry.Target) must
# be non-null for anything to happen. Returns $true if it wrote something.
function Invoke-SeedEntry {
    param([Parameter(Mandatory)]$Entry, [Parameter(Mandatory)][ValidateSet('Source','Target')][string]$Side)

    $content = if ($Side -eq 'Source') { $Entry.Source } else { $Entry.Target }
    if ($null -eq $content) { return $false }   # this side has no data for this entry

    $base     = Resolve-EntryPath $Entry.Category $Entry.RelPath
    $headerHx = ''
    if ($Entry.Header -and $script:Magic.ContainsKey($Entry.Header)) { $headerHx = $script:Magic[$Entry.Header] }
    $recorded = @()   # (fullPath) list to add to the manifest

    switch ($Entry.Kind) {
        'text' {
            Write-TextFile -Path $base -Content $content
            Set-FileAttrs -Path $base -Attrs $Entry.Attr
            $recorded += $base
        }
        'bin' {
            Write-BinFile -Path $base -Seed $content -Size $Entry.Size -HeaderHex $headerHx
            Set-FileAttrs -Path $base -Attrs $Entry.Attr
            $recorded += $base
        }
        'big' {
            Write-BinFile -Path $base -Seed $content -Size $Entry.Size -HeaderHex $headerHx
            $recorded += $base
        }
        'zero' {
            Write-BinFile -Path $base -Seed $content -Size 0
            $recorded += $base
        }
        'empty' {
            New-Dir -Path $base
            $recorded += $base
        }
        'longpath' {
            # Nest 20 folders of 30 chars each -> total path well past 260 characters.
            $seg = ('d' * 30)
            $deep = $base
            for ($i = 0; $i -lt 20; $i++) { $deep = Join-Path $deep ("{0}{1:D2}" -f $seg, $i) }
            $file = Join-Path $deep 'deep.txt'
            New-Dir -Path $deep -Long
            Write-TextFile -Path $file -Content "A file at a very long (>260 char) path." -Long
            $recorded += $file
        }
        'longname' {
            $name = ('L' * 200) + '.txt'
            $file = Join-Path $base $name
            Write-TextFile -Path $file -Content "A file with a ~200 character name." -Long
            $recorded += $file
        }
        'special' {
            foreach ($n in (Get-SpecialNames)) {
                $file = Join-Path $base $n
                Write-TextFile -Path $file -Content ("Special-character filename test: {0}" -f $n) -Long
                $recorded += $file
            }
        }
        'manysmall' {
            New-Dir -Path $base
            $count = [Math]::Max(1, $Entry.Count)
            for ($i = 1; $i -le $count; $i++) {
                $file = Join-Path $base ("file_{0:D5}.txt" -f $i)
                Write-TextFile -Path $file -Content ("tiny file #{0}" -f $i)
            }
            # Record the folder once (manifest stays small; disk has $count files).
            Add-ManifestEntry -Class $Entry.Class -Category $Entry.Category `
                -RelPath $Entry.RelPath -FullPath $base -Kind $Entry.Kind -Side $Side `
                -Attr $Entry.Attr -Note ("{0} ({1} files)" -f $Entry.Note, $count)
            return $true
        }
        default { throw "Unknown entry kind: $($Entry.Kind)" }
    }

    foreach ($fp in $recorded) {
        Add-ManifestEntry -Class $Entry.Class -Category $Entry.Category `
            -RelPath $Entry.RelPath -FullPath $fp -Kind $Entry.Kind -Side $Side `
            -Attr $Entry.Attr -Note $Entry.Note
    }
    return $true
}
