# Changelog

All notable changes to this project will be documented in this file.

## [0.0.9] - 2026-02-21

### Fixed
- Resolved `PermissionError` on `config.json` when launching from the system menu by resolving the config path relative to the executable/script location instead of the current working directory.

## [0.0.8] - 2026-02-21

### Fixed
- Suppressed console window flashes on Windows during git subprocess calls by adding `CREATE_NO_WINDOW` flag to `subprocess.run`.

### Added
- Added `git-sync-checker.spec` for reproducible PyInstaller builds.
- Added `build/` and `dist/` to `.gitignore`.

## [0.0.7] - 2026-02-21

### Added
- Integrated `icon_loader.py` from Icon_Manager_Module for cross-platform icon management.
- Added `resources/icons/` containing `app.ico`, `app.png`, and individual resolution PNGs (16–256px), generated from `app.png` via Pillow.
- Added `icons.set_taskbar_icon()` call after `window.show()` to fix Windows 11 taskbar showing default Python icon.
- Added `app.setWindowIcon(icons.app_icon())` at application level in `main()`.

### Changed
- Replaced manual `QIcon(icon_path)` / `os.path.exists()` icon setup in `MainWindow.__init__` with `icons.app_icon()`.
- Bump version to 0.0.7.

## [0.0.6] - 2026-02-21

### Added
- Added `git-sync-checker.desktop` file for system menu integration.
- Installed app icon to XDG hicolor theme at all standard sizes (16, 24, 32, 48, 64, 128, 256px).
- Added `app.setDesktopFileName()` and `app.setApplicationName()` for proper desktop environment integration.

### Changed
- Renamed `icon.png` to `app.png` per Icon_Manager_Module naming convention.
- Updated `.desktop` file to use XDG theme icon name instead of absolute path.

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
