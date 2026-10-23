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
$script:MaxHashBytes     = 256MB   # files larger than this are recorded/compared by size, not hash
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

# --------------------------------------------------------------- permissions / ACLs
#
# NTFS permissions are expressed as ACEs tied to a security identity (SID). A SID for a
# local user is machine-specific, so an ACE for "the current user" cannot be compared
# across the Source and Target PCs. The *well-known* SIDs below are byte-identical on
# every Windows machine, so ACEs built from them ARE comparable across the two PCs --
# that is what makes "were the permissions retained?" a checkable question. The
# permission scenarios therefore lean on these well-known identities.

function Get-WellKnownSid {
    param([Parameter(Mandatory)][string]$Name)
    $type = switch ($Name) {
        'Everyone'           { [System.Security.Principal.WellKnownSidType]::WorldSid }
        'Users'              { [System.Security.Principal.WellKnownSidType]::BuiltinUsersSid }
        'Administrators'     { [System.Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid }
        'AuthenticatedUsers' { [System.Security.Principal.WellKnownSidType]::AuthenticatedUserSid }
        default { throw "Unknown well-known identity: $Name" }
    }
    return (New-Object System.Security.Principal.SecurityIdentifier($type, $null))
}

# SIDs we treat as portable (same on every machine) when comparing ACLs across PCs.
$script:PortableSids = @('S-1-1-0','S-1-5-32-544','S-1-5-32-545','S-1-5-11','S-1-5-18','S-1-3-0')

# Applies one named permission scenario to an already-written file (or folder). Each
# scenario is a distinct NTFS-permission situation whose retention we want to test.
function Set-PermissionScenario {
    param([string]$Path, [string]$Scenario)
    if ($script:IsDryRun -or [string]::IsNullOrEmpty($Scenario)) { return }

    $acl = Get-Acl -LiteralPath $Path
    switch ($Scenario) {
        'deny-write-everyone' {
            $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                (Get-WellKnownSid 'Everyone'), 'Write', 'None', 'None', 'Deny')
            $acl.AddAccessRule($rule)
        }
        'deny-write-users' {
            $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                (Get-WellKnownSid 'Users'), 'Write', 'None', 'None', 'Deny')
            $acl.AddAccessRule($rule)
        }
        'grant-full-users' {
            $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                (Get-WellKnownSid 'Users'), 'FullControl', 'None', 'None', 'Allow')
            $acl.AddAccessRule($rule)
        }
        'readonly-everyone' {
            $allow = New-Object System.Security.AccessControl.FileSystemAccessRule(
                (Get-WellKnownSid 'Everyone'), 'ReadAndExecute', 'None', 'None', 'Allow')
            $deny = New-Object System.Security.AccessControl.FileSystemAccessRule(
                (Get-WellKnownSid 'Everyone'), 'Write', 'None', 'None', 'Deny')
            $acl.AddAccessRule($allow); $acl.AddAccessRule($deny)
        }
        'protected-keep' {
            # Break inheritance but COPY the inherited ACEs into explicit ones.
            $acl.SetAccessRuleProtection($true, $true)
        }
        'protected-remove' {
            # Break inheritance and REMOVE inherited ACEs; re-grant Administrators +
            # Users FullControl so the file stays usable (and gives us explicit ACEs to
            # check for retention).
            $acl.SetAccessRuleProtection($true, $false)
            foreach ($id in 'Administrators','Users') {
                $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                    (Get-WellKnownSid $id), 'FullControl', 'None', 'None', 'Allow')
                $acl.AddAccessRule($rule)
            }
        }
        'folder-inherited' {
            # On a folder: add an ACE that children inherit (ContainerInherit +
            # ObjectInherit), so we can check whether the inherited permission
            # propagates on the target too.
            $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                (Get-WellKnownSid 'Users'), 'Modify', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
            $acl.AddAccessRule($rule)
        }
        default { throw "Unknown permission scenario: $Scenario" }
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

# Best-effort: EFS can be disabled by policy and NTFS compression needs an NTFS volume.
# A failure here just means that attribute won't be set -- the retention check then
# compares "not encrypted" to "not encrypted", which is still a valid (if weaker) result.
function Set-Encrypted {
    param([string]$Path)
    if ($script:IsDryRun) { return }
    try { [System.IO.File]::Encrypt($Path) }
    catch { Write-Warn2 "could not EFS-encrypt $Path ($($_.Exception.Message)) -- continuing" }
}
function Set-Compressed {
    param([string]$Path)
    if ($script:IsDryRun) { return }
    # No .NET API for per-file NTFS compression; compact.exe is the supported tool.
    try { & compact /c /q /i "$Path" | Out-Null }
    catch { Write-Warn2 "could not NTFS-compress $Path ($($_.Exception.Message)) -- continuing" }
}

# Reads the full security state of a path into a plain object for the manifest. Captured
# at seed time on the Source; check_permissions.ps1 compares the Target against it.
function Get-SecurityInfo {
    param([string]$Path)
    try {
        $item  = Get-Item -LiteralPath $Path -Force
        $attrs = $item.Attributes
        $acl   = Get-Acl -LiteralPath $Path
        $aces  = @()
        foreach ($r in $acl.Access) {
            $sid = $null
            try { $sid = $r.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { $sid = $r.IdentityReference.Value }
            $aces += [pscustomobject]@{
                Sid        = $sid
                Identity   = $r.IdentityReference.Value
                Rights     = $r.FileSystemRights.ToString()
                Type       = $r.AccessControlType.ToString()
                Inherited  = [bool]$r.IsInherited
                Portable   = ($script:PortableSids -contains $sid)
                Inheritance= $r.InheritanceFlags.ToString()
            }
        }
        return [pscustomobject]@{
            Attributes = $attrs.ToString()
            ReadOnly   = [bool]($attrs -band [System.IO.FileAttributes]::ReadOnly)
            Hidden     = [bool]($attrs -band [System.IO.FileAttributes]::Hidden)
            System     = [bool]($attrs -band [System.IO.FileAttributes]::System)
            Encrypted  = [bool]($attrs -band [System.IO.FileAttributes]::Encrypted)
            Compressed = [bool]($attrs -band [System.IO.FileAttributes]::Compressed)
            Owner      = $acl.Owner
            Protected  = [bool]$acl.AreAccessRulesProtected
            Aces       = $aces
        }
    } catch {
        return $null
    }
}

# --------------------------------------------------------------------- manifest

# Path of FullPath relative to its category's marker root (e.g. "edge\perms\x.txt").
# Stored so check_permissions.ps1 can rebuild the Target path under the Target user's
# own profile, regardless of differing user names / drive layouts between the two PCs.
function Get-MarkerRelPath {
    param([string]$Category, [string]$FullPath)
    $root = Join-Path (Get-KnownFolder $Category) $script:MarkerFolderName
    $full = [System.IO.Path]::GetFullPath($FullPath)
    if ($full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $full.Substring($root.Length).TrimStart('\')
    }
    return $null
}

function Add-ManifestEntry {
    param(
        [string]$Class, [string]$Category, [string]$RelPath, [string]$FullPath,
        [string]$Kind, [string]$Side, [string[]]$Attr, [string]$Note,
        [string]$Scenario = '', [switch]$CaptureSecurity
    )
    $size = $null; $hash = $null; $sec = $null
    if (-not $script:IsDryRun) {
        try {
            if ([System.IO.File]::Exists($FullPath)) {
                $size = (Get-Item -LiteralPath $FullPath -Force).Length
                # Skip hashing very large files (e.g. the multi-GB big file): a 10 GB hash
                # at seed AND again at check is slow -- those are verified by size instead.
                if ($size -le $script:MaxHashBytes) {
                    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $FullPath).Hash
                }
            }
        } catch { }   # hashing a locked/odd/long-path file is best-effort only
        if ($CaptureSecurity) { $sec = Get-SecurityInfo $FullPath }
    }
    $script:Manifest.Add([pscustomobject]@{
        Class     = $Class
        Category  = $Category
        RelPath   = $RelPath
        MarkerRel = (Get-MarkerRelPath $Category $FullPath)
        FullPath  = $FullPath
        Kind      = $Kind
        Side      = $Side
        Attr      = ($Attr -join ',')
        Scenario  = $Scenario
        Size      = $size
        Sha256    = $hash
        Security  = $sec
        Note      = $Note
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
    $json = $payload | ConvertTo-Json -Depth 10
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
              [long]$Size=0,$Header='',[string[]]$Attr=@(),[int]$Count=0,$Note='',
              $Acl='',[switch]$Encrypt,[switch]$Compress)
        $P.Add([pscustomobject]@{
            Class=$Class; Category=$Category; RelPath=$RelPath; Kind=$Kind;
            Source=$Source; Target=$Target; Size=$Size; Header=$Header;
            Attr=$Attr; Count=$Count; Note=$Note;
            Acl=$Acl; Encrypt=[bool]$Encrypt; Compress=[bool]$Compress
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

    # ---- G. Source-only PERMISSION cases (does the migration retain them?) -----------
    # All use well-known SIDs so the ACEs are identical on both PCs and therefore
    # checkable by check_permissions.ps1 after the transfer.
    Add-Entry 'edge-perms' 'Documents' 'perms\readonly-attr.txt'       'text' "ReadOnly attribute set." $null -Attr @('ReadOnly') -Note 'read-only attribute retention'
    Add-Entry 'edge-perms' 'Documents' 'perms\deny-write-everyone.txt' 'text' "Everyone is DENIED Write." $null -Acl 'deny-write-everyone' -Note 'explicit Deny ACE (Everyone)'
    Add-Entry 'edge-perms' 'Documents' 'perms\deny-write-users.txt'    'text' "Users group is DENIED Write." $null -Acl 'deny-write-users' -Note 'explicit Deny ACE (Users)'
    Add-Entry 'edge-perms' 'Documents' 'perms\grant-full-users.txt'    'text' "Users group granted FullControl." $null -Acl 'grant-full-users' -Note 'explicit Allow ACE (Users)'
    Add-Entry 'edge-perms' 'Documents' 'perms\readonly-everyone.txt'   'text' "Everyone read-only (Allow RX + Deny Write)." $null -Acl 'readonly-everyone' -Note 'read-only for Everyone'
    Add-Entry 'edge-perms' 'Documents' 'perms\inherit-broken-keep.txt' 'text' "Inheritance disabled, inherited ACEs copied." $null -Acl 'protected-keep' -Note 'protected ACL, inherited copied'
    Add-Entry 'edge-perms' 'Documents' 'perms\inherit-broken-strip.txt' 'text' "Inheritance disabled, inherited ACEs removed." $null -Acl 'protected-remove' -Note 'protected ACL, inherited removed'
    Add-Entry 'edge-perms' 'Documents' 'perms\encrypted.txt'           'text' "EFS-encrypted file content." $null -Encrypt -Note 'EFS encryption retention'
    Add-Entry 'edge-perms' 'Documents' 'perms\compressed.txt'          'text' ("NTFS-compressed file. " + ('padding ' * 500)) $null -Compress -Note 'NTFS compression retention'
    # A folder whose ACE children inherit, plus a child file that should pick it up.
    Add-Entry 'edge-perms' 'Documents' 'perms\inherited-folder'        'empty' 'x' $null -Acl 'folder-inherited' -Note 'folder grants Users:Modify, inheritable'
    Add-Entry 'edge-perms' 'Documents' 'perms\inherited-folder\child.txt' 'text' "Should inherit the folder's Users:Modify ACE." $null -Note 'inheritance propagation to child'

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

    # Apply permission scenario / encryption / compression to the entry's main path.
    if ($Entry.Acl)      { Set-PermissionScenario -Path $base -Scenario $Entry.Acl }
    if ($Entry.Encrypt)  { Set-Encrypted  -Path $base }
    if ($Entry.Compress) { Set-Compressed -Path $base }

    # Capture the full security state only where it's the point of the test (keeps the
    # manifest small and avoids an ACL read per file for the many-small/bulk cases).
    $captureSec = ($Entry.Class -eq 'edge-perms') -or ($Entry.Attr.Count -gt 0) -or
                  $Entry.Acl -or $Entry.Encrypt -or $Entry.Compress

    foreach ($fp in $recorded) {
        Add-ManifestEntry -Class $Entry.Class -Category $Entry.Category `
            -RelPath $Entry.RelPath -FullPath $fp -Kind $Entry.Kind -Side $Side `
            -Attr $Entry.Attr -Note $Entry.Note -Scenario $Entry.Acl -CaptureSecurity:$captureSec
    }
    return $true
}


# --------------------------------------------------------------------- HTML reports
#
# Self-contained HTML report helpers shared by check_permissions.ps1 and
# check_collisions.ps1 -- same "the report is the only artifact" convention and visual
# language (donut, stat tiles, status badges, light/dark) as validation/'s HTML reports.

function ConvertTo-HtmlText {
    param([string]$Text)
    if ($null -eq $Text) { return '' }
    return ($Text -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;' -replace '"', '&quot;')
}

# A coloured status pill. Kind is pass | fail | warn | neutral.
function New-Badge {
    param([string]$Text, [string]$Kind = 'neutral')
    return ('<span class="badge {0}">{1}</span>' -f $Kind, (ConvertTo-HtmlText $Text))
}

function New-DonutSvg {
    param([int]$Pass, [int]$Fail)
    $total = $Pass + $Fail
    $r = 40.0
    $circ = 2 * [Math]::PI * $r
    if ($total -eq 0) { $passLen = 0.0; $failLen = 0.0; $pct = '&ndash;' }
    else { $passLen = $circ * ($Pass / $total); $failLen = $circ - $passLen; $pct = ('{0:N0}%' -f ($Pass / $total * 100)) }
    return @"
    <div class="donut-wrap">
      <svg viewBox="0 0 100 100" class="donut" role="img" aria-label="Pass rate $pct">
        <circle cx="50" cy="50" r="40" fill="none" stroke="var(--donut-track)" stroke-width="14"></circle>
        <circle cx="50" cy="50" r="40" fill="none" stroke="#d03b3b" stroke-width="14"
                stroke-dasharray="$([Math]::Round($failLen,2)) $([Math]::Round($circ,2))" stroke-dashoffset="$([Math]::Round(-$passLen,2))"
                transform="rotate(-90 50 50)"></circle>
        <circle cx="50" cy="50" r="40" fill="none" stroke="#0ca30c" stroke-width="14"
                stroke-dasharray="$([Math]::Round($passLen,2)) $([Math]::Round($circ,2))" stroke-dashoffset="0"
                transform="rotate(-90 50 50)"></circle>
        <text x="50" y="47" text-anchor="middle" class="donut-pct">$pct</text>
        <text x="50" y="62" text-anchor="middle" class="donut-sub">pass rate</text>
      </svg>
      <div class="legend">
        <div class="legend-row"><span class="dot pass"></span>OK &mdash; $Pass</div>
        <div class="legend-row"><span class="dot fail"></span>Failed &mdash; $Fail</div>
      </div>
    </div>
"@
}

$script:ReportStyle = @'
:root { color-scheme: light dark; --donut-track: #e1e0d9; }
@media (prefers-color-scheme: dark) { :root { --donut-track: #2c2c2a; } }
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 2rem; background: #fafafa; color: #1a1a1a; }
@media (prefers-color-scheme: dark) { body { background: #1a1a1a; color: #eee; } }
h1 { font-size: 1.4rem; margin-bottom: 0.25rem; }
h2 { font-size: 1.1rem; margin-top: 2rem; }
.subtitle { color: #777; margin-bottom: 1.5rem; word-break: break-all; }
.top-row { display: flex; gap: 2rem; flex-wrap: wrap; align-items: center; margin-bottom: 1.5rem; }
.summary { display: flex; gap: 1.5rem; flex-wrap: wrap; }
.stat { background: rgba(127,127,127,0.08); border-radius: 8px; padding: 0.75rem 1.25rem; min-width: 110px; }
.stat .num { font-size: 1.8rem; font-weight: 700; display: block; }
.stat.pass .num { color: #0ca30c; } .stat.fail .num { color: #d03b3b; }
.donut-wrap { display: flex; align-items: center; gap: 1rem; }
.donut { width: 110px; height: 110px; flex-shrink: 0; }
.donut-pct { font-size: 20px; font-weight: 700; fill: currentColor; }
.donut-sub { font-size: 8px; fill: #888; text-transform: uppercase; letter-spacing: 0.04em; }
.legend { font-size: 0.85rem; }
.legend-row { display: flex; align-items: center; gap: 0.4rem; margin: 0.15rem 0; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.dot.pass { background: #0ca30c; } .dot.fail { background: #d03b3b; }
.overall-badge { font-size: 1rem; font-weight: 700; padding: 0.3rem 0.9rem; border-radius: 6px; }
.overall-badge.pass { background: #dafbe1; color: #0ca30c; }
.overall-badge.fail { background: #ffebe9; color: #d03b3b; }
table { border-collapse: collapse; width: 100%; margin-top: 0.5rem; }
td, th { text-align: left; padding: 0.4rem 0.7rem; border-bottom: 1px solid rgba(127,127,127,0.15); font-size: 0.9rem; vertical-align: top; }
th { color: #888; font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em; }
.badge { font-size: 0.7rem; font-weight: 700; padding: 0.1rem 0.5rem; border-radius: 4px; white-space: nowrap; }
.badge.pass { background: #dafbe1; color: #0ca30c; }
.badge.fail { background: #ffebe9; color: #d03b3b; }
.badge.warn { background: #fff4d6; color: #a6760a; }
.badge.neutral { background: rgba(127,127,127,0.15); color: #8a8a8a; }
.mono { font-family: ui-monospace, Consolas, monospace; font-size: 0.85rem; word-break: break-all; }
.note { color: #777; font-size: 0.85rem; }
'@

# Writes one self-contained HTML report. $Stats is an array of @{num;label;kind}; $Pass
# and $Fail drive the donut + overall badge; $BodyHtml is the checker-built section(s).
function New-HtmlReport {
    param(
        [string]$Title, [string]$Subtitle, [object[]]$Stats,
        [int]$Pass, [int]$Fail, [string]$BodyHtml, [bool]$OverallOk, [string]$OutPath
    )
    $statTiles = ''
    foreach ($s in $Stats) {
        $kind = if ($s.kind) { ' ' + $s.kind } else { '' }
        $statTiles += ('<div class="stat{0}"><span class="num">{1}</span>{2}</div>' -f $kind, $s.num, (ConvertTo-HtmlText $s.label))
    }
    $overall = if ($OverallOk) { '<div class="stat"><span class="overall-badge pass">PASS</span></div>' }
               else { '<div class="stat"><span class="overall-badge fail">FAIL</span></div>' }
    $donut = New-DonutSvg -Pass $Pass -Fail $Fail
    $html = @"
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$(ConvertTo-HtmlText $Title)</title>
<style>$script:ReportStyle</style>
</head>
<body>
  <h1>$(ConvertTo-HtmlText $Title)</h1>
  <div class="subtitle">$Subtitle</div>
  <div class="top-row">
    <div class="summary">$statTiles$overall</div>
    $donut
  </div>
  $BodyHtml
</body>
</html>
"@
    $dir = [System.IO.Path]::GetDirectoryName($OutPath)
    [System.IO.Directory]::CreateDirectory($dir) | Out-Null
    [System.IO.File]::WriteAllText($OutPath, $html, $script:Utf8NoBom)
    return $OutPath
}
