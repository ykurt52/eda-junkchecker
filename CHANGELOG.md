# Changelog

## 1.0.0 — 2026-10-07

### Added

- Rule profiles in editable JSON: Altium, CircuitStudio, KiCad, FreeCAD, Office and Generic. User override file supported, and each profile can be switched on or off.
- Exclusion list of folders and glob patterns. Folders can also be excluded from the right-click menu in the results.
- Open-project protection: a banner appears while an EDA tool is running, and backups of locked projects are kept.
- Clean actions: Recycle Bin, move to archive folder, or zip archive (verified before the originals are removed).
- Undo last clean, including restore from the Recycle Bin.
- Duplicate finder tab.
- Overview tab with a treemap and reclaimed-space statistics.
- HTML and CSV report export.
- Git helper: `git rm --cached` commands and `.gitignore` suggestions.
- Cancel button for long scans. Scans skip network drives and junctions.
- Command line (`python -m junkchecker`), Task Scheduler script and Explorer context menu.
- Dark theme.
- unittest suite, PyInstaller build and GitHub Actions workflow.

## 0.2.0

### Added

- Modern flat UI.
- English and Turkish interface.
- Scan cache per folder.
- Log of scans and deletions.
- The last folder is remembered.

## 0.1.0

### Added

- First version: Altium junk scan, with deletion to the Recycle Bin.
