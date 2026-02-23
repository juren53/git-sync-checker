# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-02-23

### Added
- **Git Info dialog**: click any project name in the main window to open a drill-down dialog showing:
  - **Overview strip**: current branch, tracking branch (upstream ref), HEAD short SHA, and remote origin URL.
  - **"Latest Commit" tab**: full `git show --stat HEAD` output — commit hash, author, date, message, and per-file change stat.
  - **"Log (last 20)" tab**: `git log` in a clean columnar format — short hash, relative date, author, and subject.
  - **Refresh** button to re-run all git queries in place without reopening the dialog.
- Project name in each row is now a clickable underlined button with a pointer cursor and tooltip.
- Added `QTabWidget` to PyQt6 imports.

## [0.2.7] - 2026-02-22

### Changed
- **Help > User Guide** and **Help > Changelog** now open the `.md` files in the system's default markdown viewer/editor instead of an in-app plaintext dialog.
- **Help > About** dialog font scaled up 15% for readability.
- **About dialog system info** made more human-readable: friendlier labels ("Running as", "App location", "Operating System"), compact single-line tool entries, removed hardcoded 9pt font override.
- **README.md** rewritten to reflect all current features, installation methods, usage guide, keyboard shortcuts, and up-to-date requirements.

## [0.2.6] - 2026-02-22

### Added
- **Zoom in/out** via View menu (Ctrl++, Ctrl+-, Ctrl+0) and Ctrl+Mouse Wheel, powered by the zoom-manager module.
- Zoom level persists across sessions via QSettings.
- Status bar shows current zoom percentage on change.

### Changed
- Renamed **"Delete"** button to **"Remove"** (button label and all related dialogs).
- **Improved column alignment**: project rows now use a `QGridLayout` instead of independent `QHBoxLayout` rows; name column width is computed dynamically from the longest project name; count column tightened from 80px to 60px.

## [0.2.5] - 2026-02-22

### Added
- **Theme support** via the ThemeManager module: five built-in themes available — Dark, Light, Solarized Light, Dracula, and GitHub.
- **Theme selector** in Preferences dialog (`Edit > Preferences`); selected theme is persisted in `config.json` and applied immediately on save.
- Theme is applied on startup using Qt Fusion style with a fully customized `QPalette`.

## [0.2.4] - 2026-02-22

### Changed
- Version number restored to the window title bar.

## [0.2.3] - 2026-02-22

### Added
- **Menu bar** (File | Edit | Help) at the top of the main window.
- **File > Exit**: closes the application.
- **Edit > Preferences**: placeholder item (not yet implemented).
- **Help > Changelog**: opens `CHANGELOG.md` in a scrollable dialog.
- **Help > User Guide**: opens `README.md` in a scrollable dialog.
- **Help > About**: full About dialog powered by the `pyqt-app-info` module (`AppIdentity`, `gather_info`, `AboutDialog`), showing app version, description, feature list, and runtime environment details.

### Changed
- Renamed per-project **"Ask Claude"** button to **"Get Help"**.

## [0.2.2] - 2026-02-21

### Added
- **Ask Claude button** per project row: gathers context (current status, last sync error, uncommitted files, `git status`, recent commits) and calls `claude --print` in a background thread (`ClaudeResponseThread`).
- **Claude response dialog** (`ClaudeResponseDialog`): scrollable, read-only monospace text area showing Claude's suggestion, with Copy and Close buttons.
- Button shows `⏳ Asking...` while the request is in flight and re-enables on completion.
- Graceful error handling for missing CLI (`claude` not on PATH), timeouts (60 s), and non-zero exit codes.

## [0.2.1] - 2026-02-21

### Fixed
- Sync failure status label now reads "❌ Sync failed — ask Claude Code?" to guide users toward help.
- Error message persists as a hover tooltip on the status label after the dialog is dismissed.
- Warning dialog appends "Tip: ask Claude Code to help fix this."
- Tooltip is cleared automatically on the next successful status refresh.
- Updated `.desktop` `Exec` to point to installed binary (`~/.local/bin/git-sync-checker`) instead of `run.sh`.

## [0.2.0] - 2026-02-21

### Added
- **Dirty tree detection**: `check_git_sync` now runs `git status --porcelain` and returns a `dirty` flag; repos with uncommitted changes show a `⚠` indicator next to their status (orange-yellow for synced+dirty repos).
- **Stash-sync dialog** (`DirtyConflictDialog`): when Sync is clicked on a dirty+behind repo, a modal dialog lists the uncommitted files and offers "Stash → Pull → Restore" or "Cancel".
- **`GitStashSyncThread`**: background thread that runs `git stash` → `git pull --ff-only` → `git stash pop`, handling all four outcome combinations (both ok, pull ok/pop failed, pull failed/stash restored, both failed).
- **Persistent logging** (`SyncLogger`): sync events (dirty detections, user decisions, sync results) are appended to `sync_history.json`, capped at 200 entries.
- **History dialog** (`SyncHistoryDialog`): scrollable read-only log viewer, newest-first, with colour-coded event entries; opened via a new "History" button.
- After a successful sync the app triggers a full re-check so dirty state and commit counts reflect the true post-sync state.

## [0.1.0] - 2026-02-21

### Added
- Added per-project **Sync** button that runs `git pull --ff-only` in a background thread.
- Sync button is enabled only when a repo is in "Behind" state; disabled otherwise.
- On success the row updates to "✓ In Sync". On failure the button re-enables and a warning dialog shows the error output.

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
