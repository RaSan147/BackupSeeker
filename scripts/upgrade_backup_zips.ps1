#!/usr/bin/env pwsh
# Refresh _backupseeker portable CLI/embed and embedded plugins (restore_cli.py uses interactive stdin — no CLI arguments).
Set-Location (Join-Path $PSScriptRoot "..")
python -m BackupSeeker.archive.upgrade_zip backups @args
