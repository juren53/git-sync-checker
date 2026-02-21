# Changelog

All notable changes to this project will be documented in this file.

## [0.0.5] - 2026-02-21

### Added
- Added `Icon_Manager_Module` to the default project list.
- Added application window icon (`icon.png`) sourced from `Icon_Manager_Module/workshop/ICON_check-2.png`.

## [0.0.4] - 2026-02-21

### Fixed
- Expand tilde in project path when adding a new project via the dialog, fixing false 'error' status on first check after adding a project (before app restart).

## [0.0.3] - 2026-02-21

### Fixed
- Use `@{u}` instead of `origin/HEAD` when comparing against the upstream branch, fixing false 'error' status for repos where `origin/HEAD` is not set.

## [0.0.2] - 2026-02-20

### Added
- Introduced `config.json` for persistent project storage.
- Implemented UI for adding new projects via `QFileDialog`.
- Introduced `run.sh` script to automate application setup (virtual environment creation, dependency installation) and execution, improving portability and ease of use.

### Changed
- Refactored `git_sync_checker.py` to use cross-platform path handling for project directories, replacing hardcoded Windows paths with `os.path.expanduser` and `os.path.join`.
- Bump version to 0.0.2
- Implemented UI for deleting existing projects.
- Refactored project loading and UI rendering to be dynamic, supporting additions and removals.

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
