@echo off
REM Refresh _backupseeker portable CLI/embed and embedded plugins for all backups (interactive stdin restore; no CLI args).
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."
python -m BackupSeeker.archive.upgrade_zip backups %*
