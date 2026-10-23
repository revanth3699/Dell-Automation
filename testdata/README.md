# testdata — migration test-data seeding (Source PC + Target PC)

These PowerShell scripts seed a **deterministic file dataset** into the standard Windows
user-profile folders so a Dell Data Assistant PC-to-PC migration can be exercised against
real data and all its awkward edge cases — name collisions, identical files, folder
merges, skipped files, and capacity limits.

This framework drives the **real Dell app**; it does not move files itself. So "test data"
means *files on disk* that the app then migrates. After a run, verify the outcome the usual
way with [`validation/validate_migration.py`](../validation/validate_migration.py) (it
checks the Dell PDF report's *Files copied / Files not migrated* against the live disk).

Everything is written under a single marker sub-folder — `DellMigrateTest` — inside each
profile folder (`Documents`, `Desktop`, `Downloads`, `Pictures`, `Music`, `Videos`), so
cleanup never touches your real files.

## Files

| File | Role |
|---|---|
| `seed_source.ps1` | Run on the **Source (old) PC** — writes the data to be migrated + all edge/stress/permission cases. |
| `seed_target.ps1` | Run on the **Target (new) PC** — writes pre-existing data that collides with the Source's. |
| `check_permissions.ps1` | Run on the **Target PC after migration** — checks whether file permissions survived. |
| `clean.ps1` | Run on **both** PCs afterward — removes every `DellMigrateTest` folder (and nothing else). |
| `_common.ps1` | Shared library + the single data plan both seed scripts consume (keeps paths aligned). |
| `output/` | Per-run JSON manifests (hashes/sizes/**security state** of what was written) + the permission-check report — git-ignored. |

## Usage

```powershell
# On the TARGET (new) PC, BEFORE pairing — lay down the pre-existing/conflicting data:
powershell -ExecutionPolicy Bypass -File testdata\seed_target.ps1 -Profile Standard

# On the SOURCE (old) PC — lay down everything to be migrated:
powershell -ExecutionPolicy Bypass -File testdata\seed_source.ps1 -Profile Standard

# ...run the migration, then validate on the Target:
uv run python -m validation.validate_migration

# Afterward, on BOTH PCs:
powershell -ExecutionPolicy Bypass -File testdata\clean.ps1 -Force
```

Preview without writing anything: add `-DryRun` to either seed script.

> Use the **same `-Profile` on both PCs** so the conflict / identical / same-folder cases
> land on identical relative paths across the two machines.

### Parameters

- `-Profile Minimal|Standard|Stress` — volume knob.
  - **Minimal**: 20 tiny files, no large file (fast smoke test).
  - **Standard**: 200 tiny files + a 256 MB file.
  - **Stress**: 5000 tiny files + a 2 GB file (for capacity / does-not-fit).
- `-ManySmallCount <n>` / `-BigFileMB <mb>` — override the two volume cases directly.
- `-IncludeLocked` (source only) — also create a file held exclusively open by a background
  process, so the migration hits a genuinely in-use file. `clean.ps1` stops the holder.
  `-LockMinutes <n>` sets how long it stays locked (default 30).
- `-DryRun` — list planned actions, write nothing.

## Edge cases covered

The dataset is organized into taxonomy folders so results are easy to audit. Content is
tagged `SOURCE` / `TARGET` where relevant, so after migration you can tell which side won.

| Folder (under each profile folder's `DellMigrateTest\`) | What it tests |
|---|---|
| `source-only\` | Clean transfers — one file of each category (txt, pdf, xlsx, jpg, png, mp3, mp4). Must land on the Target. |
| `conflict\` | **Same path on both PCs, different content** — forces the app's conflict resolution (overwrite / rename / skip). |
| `identical\` | **Same path, byte-for-byte identical** — de-dup / skip-as-identical behavior. |
| `shared-folder\` | **Same folder name on both PCs, different filenames** — expect a merge (union). Includes one nested same-name/different-content file. |
| `target-only\` | Pre-existing Target data that must **survive** the migration untouched. |
| `edge\empty-folder\` | Empty directory (nothing to copy). |
| `edge\zero-byte.dat` | 0-byte file. |
| `edge\deep\...` | Path well past the legacy **260-char** limit. |
| `edge\longname\` | ~200-character filename. |
| `edge\special\` | Accented, emoji, bracketed, and shell-special (`& ; =`) filenames. |
| `edge\attrs\` | **Hidden**, **read-only**, and **system+hidden** files. |
| `edge\archive.zip`, `edge\tool.exe` | Archive + executable types (the `.exe` may be skipped by app policy). |
| `edge\many-small\` | Flood of tiny files — stresses counting / progress / the skipped-files path. |
| `edge\bigfile.bin` | Large file — stresses throughput and the **"free up … to continue"** does-not-fit warning. |
| `edge\locked\inuse.txt` | (with `-IncludeLocked`) genuinely in-use file — should surface in **Skipped files**. |

Generated binaries carry correct magic bytes for their extension (enough for category
detection) but are **test files, not valid playable media**.

### Permission cases (`perms\`, Source only)

These test whether **NTFS permissions / ACLs survive the migration**. All ACEs use
**well-known SIDs** (Everyone, Users, Administrators) so they're identical on both PCs and
can actually be compared across machines — a local-user SID would differ and be
uncheckable.

| File (under `Documents\DellMigrateTest\perms\`) | What it tests |
|---|---|
| `readonly-attr.txt` | Read-only attribute retention. |
| `deny-write-everyone.txt` | Explicit **Deny Write** ACE for Everyone. |
| `deny-write-users.txt` | Explicit **Deny Write** ACE for the Users group. |
| `grant-full-users.txt` | Explicit **Allow FullControl** ACE for Users. |
| `readonly-everyone.txt` | Allow Read&Execute + Deny Write for Everyone (read-only for all). |
| `inherit-broken-keep.txt` | Inheritance **disabled, inherited ACEs copied** (protected ACL). |
| `inherit-broken-strip.txt` | Inheritance **disabled, inherited ACEs removed** (only explicit remain). |
| `encrypted.txt` | **EFS-encrypted** file. |
| `compressed.txt` | **NTFS-compressed** file. |
| `inherited-folder\` + `child.txt` | Folder grants an **inheritable** Users:Modify ACE; the child should inherit it. |

> EFS and NTFS compression are best-effort — if the machine/volume doesn't support them,
> seeding continues and that one attribute simply isn't set.

## Verifying what won a conflict

Each run writes `output/<role>_manifest_latest.json` with the SHA-256 and size of every
file it created (plus the captured **security state** of the permission/attribute files).
To see which version survived a conflict, compare a Target file's current hash on disk
against the `source_` vs `target_` manifest hash for the same `RelPath`.

## Checking permission retention after migration

The Source seed captures each permission file's attributes, ACL, owner, and EFS/compression
state into `source_manifest_latest.json`. After the migration, run the checker **on the
Target PC** to compare the migrated files against that captured state:

```powershell
# 1) Copy the Source manifest to the Target PC. The migration does NOT carry it (it lives
#    outside the user profile), so copy it yourself, e.g. to C:\from_source\.
# 2) On the Target PC, after the migration completes:
powershell -ExecutionPolicy Bypass -File testdata\check_permissions.ps1 `
    -SourceManifest C:\from_source\source_manifest_latest.json
```

It prints `RETAINED` / `CHANGED` / `MISSING` per file (with the exact difference), writes
`output\permission_check_<timestamp>.json`, and exits non-zero if anything changed.

What it compares:
- **Attribute bits** — ReadOnly, Hidden, System, Encrypted, Compressed (Archive is ignored
  because copying sets it).
- **Inheritance-protected** flag.
- **Explicit ACEs built from well-known SIDs** — a local-user ACE can't be matched across
  machines, so only these portable ACEs are checked. Inherited ACEs are skipped (they
  depend on the target's own parent folders).

> Caveat: for an EFS-encrypted file the checker only confirms the *Encrypted attribute*
> survived — not that the Target user can actually decrypt it (EFS keys are per-user).

## Notes / gotchas

- **PowerShell 5.1 compatible.** Non-ASCII filenames are built from code points at runtime,
  so the scripts need no BOM.
- Run `clean.ps1` on a PC **before** re-seeding it to start from a known-empty state.
- The large file is skipped automatically if the target drive lacks ~110% of its size free.
- `clean.ps1` resets ACLs (`icacls /reset`) and uses a robocopy mirror-empty pass so it can
  delete the >260-char tree, the read-only/system files, and the Deny-ACE/protected-ACL
  permission files that plain `Remove-Item` cannot.
- These are standalone setup scripts. If you want them driven from the state-machine
  scenario runner's `setup:` / `teardown:`, they can be wrapped as steps in
  [`utils/environment.py`](../utils/environment.py) — ask and I'll add `seed_source_data`
  / `seed_target_data` / `clean_test_data` entries.
```
