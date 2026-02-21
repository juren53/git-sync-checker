# Changelog

All notable changes to this project will be documented in this file.

## [0.0.1] - 2026-02-20

### Added
- Initial release
- Display sync status for 5 projects: HST-Metadata, MDviewer, JAUs-Systems, tag-writer, system-monitor
- Shows ahead/behind commit counts
- Color-coded status indicators (synced, ahead, behind, diverged)
- Refresh button to manually check all repos
- Background thread for non-blocking git operations

### Changed
- Refactored `git_sync_checker.py` to use cross-platform path handling for project directories, replacing hardcoded Windows paths with `os.path.expanduser` and `os.path.join`.

### Added
- Introduced `run.sh` script to automate application setup (virtual environment creation, dependency installation) and execution, improving portability and ease of use.
