---
description: Kill any running TargetPC.UI instance and relaunch it against the GlassFloor mock server
---

Launch the Target PC app for manual/GlassFloor testing:

1. Stop any existing `DellDataAssistant.TargetPc` process (it's single-instance and will
   silently no-op a new launch's CLI args if one is already running):
   ```powershell
   Get-Process -Name "DellDataAssistant*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
   ```
2. Confirm something is listening on `127.0.0.1:8443` (the GlassFloor mock server). If not,
   start it first: `cd C:\Users\revan\Downloads\GlassFloor-TestPackage\SupportAssistRaceHarness; node server.js 8443 "<secret>"` (run_in_background).
3. Launch the app elevated, since it requires admin rights:
   ```powershell
   Start-Process -FilePath "C:\Users\revan\Downloads\027df3321\Release\DellDataAssistant.TargetPc.exe" `
     -ArgumentList "<secret>", "C:\Users\revan\Downloads\GlassFloor-TestPackage\SupportAssistRaceHarness\cert.pfx", "127.0.0.1:8443" `
     -Verb RunAs -PassThru | Select-Object Id, ProcessName, StartTime
   ```
   Default `<secret>` is `my-secret-active`. If arguments are given to this command
   (`$ARGUMENTS`), use that as the secret instead (e.g. `my-secret-expired-30`,
   `my-secret-active-gold`) — see SV_HANDOFF.md's secret keyword reference for valid values.
4. Wait ~3 seconds, then confirm the new process is alive and responding
   (`Get-Process -Id <id> | Select Responding`).

Arguments passed to this command: $ARGUMENTS
