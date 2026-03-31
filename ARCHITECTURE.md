# Git Sync Checker — System Architecture

**Version:** 0.6.3
**Date:** 2026-03-28
**Stack:** Python 3.8+ · PyQt6 · Git · PyInstaller

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Repository Layout](#2-repository-layout)
3. [Dependencies](#3-dependencies)
4. [Module Responsibilities](#4-module-responsibilities)
5. [Class Hierarchy](#5-class-hierarchy)
6. [Threading Model](#6-threading-model)
7. [Data Flow](#7-data-flow)
8. [UI Structure](#8-ui-structure)
9. [Configuration & Persistence](#9-configuration--persistence)
10. [External Service Integrations](#10-external-service-integrations)
11. [Platform Abstractions](#11-platform-abstractions)
12. [Build System](#12-build-system)
13. [Key Design Patterns](#13-key-design-patterns)
14. [Data Structures Reference](#14-data-structures-reference)

---

## 1. Project Overview

Git Sync Checker (GSC) is a PyQt6 desktop application that gives a single-pane view of multiple local Git repositories and their sync status relative to their remotes. It supports:

- Parallel background status checks across all tracked repos
- Pull workflows (with dirty-state handling via stash or commit/push)
- Drill-down Git information in a 13-tab dialog
- Persistent event logging with a history viewer
- Claude Code CLI integration ("Get Help" diagnosis per repo)
- GitHub CLI integration (scan for untracked recently-active repos)
- Theme system (5 built-in themes) with per-app zoom scaling
- Single-instance enforcement and per-dialog geometry persistence

---

## 2. Repository Layout

```
git-sync-checker/
├── git_sync_checker.py      # Main application (2,060 lines)
├── icon_loader.py           # Cross-platform icon management (272 lines)
├── theme_manager.py         # Theme registry and palette generation (360 lines)
├── zoom_manager.py          # Font scaling and zoom persistence (257 lines)
├── requirements.txt         # Python dependencies
├── git-sync-checker.spec    # PyInstaller build spec
├── run.ps1                  # PowerShell venv launcher (Windows)
├── CHANGELOG.md             # Release history (bundled in exe)
├── README.md                # User guide (bundled in exe)
└── resources/
    └── icons/
        ├── app.ico          # Windows taskbar icon
        ├── app.icns         # macOS dock icon
        └── *.png            # Multi-resolution PNGs (16–256 px, Linux)
```

**Total custom code:** ~2,950 lines across 4 source modules.

---

## 3. Dependencies

### Python Packages (`requirements.txt`)

| Package | Version | Purpose |
|---------|---------|---------|
| `PyQt6` | ≥6.5.0 | UI framework (widgets, threading, signals) |
| `markdown` | ≥3.4 | Markdown-to-HTML for DocViewerDialog |
| `pyqt-app-info` | local editable | App metadata helpers |

### External Binaries (runtime, optional)

| Binary | Feature | Absence behaviour |
|--------|---------|-------------------|
| `git` | All git operations | Error shown per-repo |
| `claude` | "Get Help" diagnosis | Error dialog |
| `gh` (GitHub CLI) | "Scan GitHub" feature | Error dialog |

---

## 4. Module Responsibilities

### `git_sync_checker.py`
The monolithic application entry point. Contains:
- All UI classes (`MainWindow`, every dialog)
- All worker thread classes
- Git subprocess helpers (`run_git_command`, `check_git_sync`)
- `SyncLogger` event-log utility
- Module-level global state (`PROJECT_PATHS`, `PROJECT_NAMES`)
- `main()` entry point with single-instance guard

### `icon_loader.py` — `IconLoader`
Cross-platform icon resolution:
- `.ico` on Windows (+ COM taskbar property store via `ctypes`)
- `.icns` on macOS
- Multi-resolution PNG set on Linux
- `set_taskbar_icon(window, app_id)` — Windows `WM_SETICON` + AppUserModelID

### `theme_manager.py` — `ThemeRegistry`
- Defines 5 built-in themes: **Dark**, **Light**, **Solarized Light**, **Dracula**, **GitHub**
- Each theme has a `ThemeColors` record (content colours) and a `UIPalette` record (widget colours)
- `get_fusion_palette(name)` → `QPalette` applied at app level via `app.setPalette()`
- `get_search_css(name)` → CSS string for search result highlighting

### `zoom_manager.py` — `ZoomManager` (singleton)
- 8 discrete zoom levels: 75 · 85 · 100 · 115 · 130 · 150 · 175 · 200 %
- `initialize_base_font()` — captures app base font size on startup
- `set_zoom_level(index)` — scales app-wide font, emits `zoom_changed(factor)` signal
- Persists zoom to `QSettings` (`ui/zoom_level`)

---

## 5. Class Hierarchy

```
QMainWindow
└── MainWindow
      Owns:
        ├── ZoomManager (singleton, shared)
        ├── SyncLogger (static utility)
        └── project_widgets: dict[name → row widget dict]

QThread (worker threads)
├── GitCheckThread          parallel status scan (all repos)
├── GitSyncThread           git pull --ff-only (single repo)
├── GitStashSyncThread      stash → pull → stash-pop (single repo)
├── GitPushThread           git push (inside UncommittedChangesDialog)
├── ClaudeResponseThread    claude --print (single repo)
└── GitHubScanThread        gh repo list (global scan)

QDialog
├── GitInfoDialog           13-tab drill-down per repo
├── UncommittedChangesDialog per-file stage/discard/commit/push
├── SyncPreviewDialog       shows incoming changes before pull
├── SyncHistoryDialog       persistent event log viewer
├── ClaudeResponseDialog    displays Claude CLI response
├── GitHubScanDialog        lists untracked repos from GitHub
├── PreferencesDialog       theme, auto-refresh, auto-check settings
└── DocViewerDialog         themed markdown renderer (Changelog, README)
```

---

## 6. Threading Model

All background I/O runs in `QThread` subclasses. Signals are automatically marshalled back to the main thread by Qt, so all UI updates happen safely.

| Thread | Signals emitted | Key git commands |
|--------|----------------|-----------------|
| `GitCheckThread` | `result_ready(name, status, ahead, behind, dirty, stash_count, version)` | `fetch --all`, `rev-parse`, `rev-list --count`, `status --porcelain`, `stash list`, `describe --tags` |
| `GitSyncThread` | `sync_done(name, success, message)` | `pull --ff-only` |
| `GitStashSyncThread` | `sync_done(name, success, message)` | `stash`, `pull --ff-only`, `stash pop` |
| `GitPushThread` | `push_done(success, message)` | `push` |
| `ClaudeResponseThread` | `response_ready(name, success, response)` | — (spawns `claude --print`) |
| `GitHubScanThread` | `scan_done(repos, error)` | — (spawns `gh repo list --json`) |

**Active thread tracking:** `MainWindow` holds `_sync_threads`, `_stash_threads`, and `_claude_threads` lists. Finished threads are removed on `finished` signal to prevent double-starts and allow clean shutdown.

---

## 7. Data Flow

### 7.1 Startup

```
main()
  ├── Single-instance guard (QLocalServer / QLocalSocket)
  ├── load_projects()  ──→  PROJECT_PATHS, PROJECT_NAMES (globals)
  ├── load_preferences()  ──→  theme, auto_refresh_interval
  ├── ThemeRegistry.apply()  ──→  app.setPalette()
  ├── ZoomManager.apply_saved_zoom()
  └── MainWindow.__init__()
        └── _initialize_project_ui()  creates one row widget per project
        └── [if auto_check_on_launch] start_check()
        └── [if auto_refresh_interval > 0] start QTimer
```

### 7.2 Status Check Cycle

```
Trigger: Refresh button | F5 | QTimer | window show
  ↓
MainWindow.start_check()
  ├── Disable Refresh button
  └── Spawn GitCheckThread
        ↓ (background, per repo in sequence)
        check_git_sync(repo_path)
          git fetch --all
          git rev-parse HEAD / @{u}
          git rev-list --count ahead/behind
          git status --porcelain  →  dirty flag
        git stash list             →  stash_count
        git describe --tags        →  version string
        ↓
        result_ready signal (per repo)
          ↓
        on_result_ready(name, status, ahead, behind, dirty, stash_count, version)
          → update row: status badge colour, count label, Sync button state
          → cache in _dirty_state, _last_results
        ↓
        finished signal (all repos done)
          ↓
        on_finished()
          → re-enable Refresh button
          → update "Last refreshed: HH:MM:SS" label
```

**Status states:**

| State | Colour | Meaning |
|-------|--------|---------|
| `synced` | Green ✓ | Local HEAD == remote HEAD |
| `ahead` | Blue ↑ | Local has unpushed commits |
| `behind` | Orange ↓ | Remote has new commits |
| `diverged` | Red ⇅ | Both sides diverged |
| `error` | Grey | Repo not found or no remote |

Dirty overlay: yellow ⚠ appended to any state.
Stash overlay: 📦 tooltip if stash_count > 0.

### 7.3 Sync Workflow

```
User clicks Sync (repo is "behind")
  ↓
SyncPreviewDialog  →  show incoming files (git diff HEAD..@{u} --name-status)
User confirms
  ↓
[If dirty] UncommittedChangesDialog
  ├── Per-file: Diff | Stage | Discard
  ├── Bottom: Commit Staged | Push | Stash→Pull→Restore | Close
  └── Returns: CLOSE_ACTION | STASH_ACTION | COMMITTED_ACTION
      │
      ├── STASH_ACTION  →  GitStashSyncThread
      │     git stash
      │     git pull --ff-only
      │     git stash pop
      │     → on_sync_done → SyncLogger.log → re-check
      │
      ├── COMMITTED_ACTION  →  re-check entire project
      │
      └── CLOSE_ACTION  →  SyncLogger.log("cancel") → return

[If clean] GitSyncThread
  git pull --ff-only
  → on_sync_done → SyncLogger.log → re-check
```

### 7.4 Event Logging

Every significant action emits to `SyncLogger.log(entry)`:

```
entry = {
  "event":   "sync_result" | "dirty_detected" | "dirty_conflict" | "user_action",
  "project": "<name>",
  "success": true | false,
  "message": "<detail>",
  "timestamp": "2026-03-28T14:23:01"  ← added by SyncLogger
}
→ sync_history.json  (newest first, capped at 200 entries)
```

---

## 8. UI Structure

### 8.1 Main Window

```
┌─────────────────────────────────────────────────────────┐
│  Project Sync Status              Last refreshed: 14:23  │  header
├─────────────────────────────────────────────────────────┤
│                    [ Refresh (F5) ]                      │
├──────────────┬──────────┬──────────────┬────────────────┤
│ Name         │ Version  │ Status       │ Count  Actions  │  column headers
├──────────────┼──────────┼──────────────┼────────────────┤
│ repo-a       │ v1.2.3   │ ✓ In Sync   │        Sync    │
│              │          │              │        Help    │
│              │          │              │        Remove  │
├──────────────┼──────────┼──────────────┼────────────────┤
│ repo-b       │ v2.0.0   │ ↓ Behind  ⚠ │  −5    Sync    │
│              │          │              │   📦   Help    │
│              │          │              │        Remove  │
└─────────────────────────────────────────────────────────┘
Status bar: "Zoom: 150%" | "Scanning GitHub…" | ""
```

### 8.2 Menu Bar

```
File
  └── Exit

Edit
  ├── Add Project
  ├── Scan GitHub for New Projects…
  └── Preferences

View
  ├── Refresh          F5
  ├── Zoom In          Ctrl++
  ├── Zoom Out         Ctrl+-
  ├── Reset Zoom       Ctrl+0
  └── History

Help
  ├── Changelog
  ├── User Guide
  ├── Issue Log
  └── About
```

### 8.3 GitInfoDialog — *"Git Info — \<project\>"*

```
┌───────────────────────────────────────────────────────────┐
│  Branch: main    Tracking: origin/main    [ Open Folder ] │  overview strip
│  HEAD: abc1234   URL: https://…           [ Copy URL ]    │
├───────────────────────────────────────────────────────────┤
│ [Latest Commit][Log][Git Show][Diff][Status][Stash]…      │  tab bar
├───────────────────────────────────────────────────────────┤
│  (monospace themed text area)                             │
├───────────────────────────────────────────────────────────┤
│  [−] [100%] [+]    [ Refresh ]    [ Close ]               │
└───────────────────────────────────────────────────────────┘
```

| # | Tab | Git command |
|---|-----|-------------|
| 1 | Latest Commit | `git show --stat HEAD` |
| 2 | Log (last 20) | `git log --pretty=format:… -20` |
| 3 | Git Show | `git show HEAD` (full patch) |
| 4 | Git Diff | `git diff` (unstaged) |
| 5 | Git Status | `git status` |
| 6 | Git Stash | `git stash list` |
| 7 | Git Remote | `git remote -v` |
| 8 | Git Branches | `git branch -a -vv` |
| 9 | Git Tags | `git tag -n` |
| 10 | Git Config | `git config --local --list` |
| 11 | Git Log | `git log --oneline --graph --decorate --all` |
| 12 | Git Blame | interactive: file browser + `git blame` |
| 13 | Git Grep | interactive: pattern + glob + `git grep` |
| 14 | Git Shortlog | `git shortlog -sne --all` |

### 8.4 UncommittedChangesDialog — *"Uncommitted Changes — \<project\>"*

Opened when the user tries to sync a repo that has a dirty working tree. Provides per-file actions before deciding how to proceed.

```
┌──────────────────────────────────────────────────────────┐
│  <project> has N uncommitted change(s).                  │  info label
├──────────────────────────────────────────────────────────┤
│  (scrollable, max 240 px)                                │
│  [M]  src/foo.py        [----] [Stage] [Discard]         │  per-file row
│  [??] scratch.txt       [----] [Stage] [Discard]         │  (untracked)
│  [D]  old_file.py       [----] [Stage] [Discard]         │
├──────────────────────────────────────────────────────────┤
│  Commit message: [___________________________________]   │
│  [ Commit Staged ]  [ Push ]                             │
│  (status line — green on success, red on failure)        │
├──────────────────────────────────────────────────────────┤
│  [ Stash → Pull → Restore ]              [ Close ]       │
└──────────────────────────────────────────────────────────┘
```

**File status badge colours:** Added `#28a745`, Modified `#fd7e14`, Deleted `#dc3545`, New/Untracked `#adb5bd`.

**Return values (`chosen_action()`):**

| Constant | Value | Meaning |
|----------|-------|---------|
| `CLOSE_ACTION` | 0 | User dismissed — do not sync |
| `STASH_ACTION` | 1 | Proceed with `GitStashSyncThread` |
| `COMMITTED_ACTION` | 2 | User committed or pushed inside the dialog |

**Diff sub-dialog:** clicking "Diff" on a tracked file opens a plain `QDialog` with a read-only `QPlainTextEdit` showing both unstaged (`git diff -- <file>`) and staged (`git diff --cached HEAD -- <file>`) diff output.

### 8.5 SyncPreviewDialog — *"Files to Sync — \<project\>"*

Modal confirmation step shown before every pull, listing all files that will change.

```
┌──────────────────────────────────────────────────────────┐
│  <project>: N file(s) will be updated from remote:       │
├──────────────────────────────────────────────────────────┤
│  (scrollable, max 220 px)                                │
│  M  src/main.py                                          │  colour-coded
│  A  src/new_feature.py                                   │  per status char
│  D  src/old.py                                           │
├──────────────────────────────────────────────────────────┤
│  A=added   M=modified   D=deleted   R/C=renamed/copied   │  legend
├──────────────────────────────────────────────────────────┤
│                              [ Sync ]  [ Cancel ]        │
└──────────────────────────────────────────────────────────┘
```

File colour map: `A` → green, `M` → orange, `D` → red, `R`/`C` → teal.
If no individual file changes are detected the scrollable list is omitted and a plain message is shown instead.
Geometry is persisted to `config.json` under key `"sync_preview"`.

### 8.6 SyncHistoryDialog — *"Sync History"*

Read-only log viewer for `sync_history.json`. Opened from View → History.

```
┌──────────────────────────────────────────────────────────┐
│  Sync History (newest first)                             │  bold heading
├──────────────────────────────────────────────────────────┤
│  (scrollable list of framed entries)                     │
│  ┌──────────────────────────────────────────────────┐   │
│  │  2026-03-28T14:23:01 — repo-a         (grey)     │   │
│  │  Sync succeeded                       (green)    │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │  2026-03-28T13:55:12 — repo-b         (grey)     │   │
│  │  Dirty tree detected                  (yellow)   │   │
│  └──────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────┤
│                                          [ Close ]       │
└──────────────────────────────────────────────────────────┘
```

**Entry colour coding:**

| Event | Colour |
|-------|--------|
| `dirty_detected` | Yellow `#e6ac00` |
| `dirty_conflict` | Orange `#fd7e14` |
| `user_action` → stash | Blue `#007bff` |
| `user_action` → cancel | Grey `#888888` |
| `sync_result` success | Green `#28a745` |
| `sync_result` failure | Red `#dc3545` |

Geometry persisted under key `"sync_history"`.

### 8.7 PreferencesDialog — *"Preferences"*

Three-field form dialog opened from Edit → Preferences. Changes take effect immediately after OK.

```
┌─────────────────────────────────────────────────────┐
│  Auto-refresh interval:  [ 5 ▲▼ ] min               │  QSpinBox 0–120;
│                           (0 shows "Disabled")      │
│  Auto-check on launch:   [✓]                        │  QCheckBox
│  Theme:                  [ Dark          ▼]         │  QComboBox (5 items)
├─────────────────────────────────────────────────────┤
│                              [ OK ]  [ Cancel ]     │
└─────────────────────────────────────────────────────┘
```

`get_preferences()` returns `{"auto_refresh_interval": int, "auto_check_on_launch": bool, "theme": str}`.

### 8.8 ClaudeResponseDialog — *"Claude's Suggestion — \<project\>"*

Displays the response from the Claude Code CLI for a single project. Opened after `ClaudeResponseThread` completes.

```
┌─────────────────────────────────────────────────────┐
│  Claude's suggestion for <project>:                 │
├─────────────────────────────────────────────────────┤
│  (read-only monospace QTextEdit)                    │
│  ...Claude output...                                │
├─────────────────────────────────────────────────────┤
│  [ Copy ]  [ Close ]                                │
└─────────────────────────────────────────────────────┘
```

"Copy" writes the full response text to the system clipboard via `QApplication.clipboard()`.

### 8.9 GitHubScanDialog — *"GitHub Scan — Untracked Active Repos"*

Opened after `GitHubScanThread` completes (Edit → Scan GitHub for New Projects…). Lists repos active in the last 7 days that are not already tracked in GSC.

```
┌───────────────────────────────────────────────────────────────┐
│  Found N GitHub repo(s) with commits in the last 7 days       │
│  that are not in your GSC project list:                        │
├───────────────────────────────────────────────────────────────┤
│  (scrollable list, sorted newest-pushed first)                │
│  owner/repo-a        v1.2.3    2026-03-27   [ Open ]          │
│  owner/repo-b        —         2026-03-25   [ Open ]          │
├───────────────────────────────────────────────────────────────┤
│                                              [ Close ]        │
└───────────────────────────────────────────────────────────────┘
```

Columns: name (240 px), version tag (90 px, grey), pushed date (90 px, grey), Open button (55 px).
"Open" calls `QDesktopServices.openUrl()` with the repo's GitHub URL.
If all active repos are already tracked, the list is replaced with a plain "nothing to add" message.

### 8.10 DocViewerDialog — *"Changelog" / "User Guide"*

Themed markdown renderer used for Help › Changelog and Help › User Guide.

```
┌─────────────────────────────────────────────────────┐
│  (QTextBrowser — rendered HTML, external links on)  │
│  # Changelog                                        │
│  ## v0.6.3 ...                                      │
│  ...                                                │
├─────────────────────────────────────────────────────┤
│  Source: bundled file                (italic, grey)  │
├─────────────────────────────────────────────────────┤
│                              [ Close ]              │
└─────────────────────────────────────────────────────┘
```

Three-tier content fallback (in order):
1. Bundled file via `sys._MEIPASS` (frozen exe) or `_base_dir` (source run)
2. GitHub raw URL via `urllib.request.urlopen(timeout=10)`
3. Plain text if `markdown` library is unavailable

Theme detection: checks `QPalette.ColorRole.Window` brightness (average RGB < 128 → dark). Dark mode uses `#1e1e1e` background; light mode uses `#ffffff`. Source note line is omitted when no fallback was needed.

---

## 9. Configuration & Persistence

### 9.1 `config.json` (app directory)

```json
{
  "projects": ["~/path/to/repo1", "~/path/to/repo2"],
  "preferences": {
    "auto_refresh_interval": 5,
    "auto_check_on_launch": true,
    "theme": "dark"
  },
  "window_geometry": {
    "main":     {"x": 100, "y": 200, "width": 800, "height": 600},
    "git_info": {"x": 150, "y": 250, "width": 900, "height": 700}
  }
}
```

Read by `load_projects()` / `load_preferences()` / `load_window_geometry()`.
Written by `save_projects()` / `save_preferences()` / `save_window_geometry()`.

### 9.2 `sync_history.json` (app directory)

Array of event entry objects (see §7.4), newest first, capped at 200 entries.
Managed exclusively by `SyncLogger`.

### 9.3 Qt QSettings

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `ui/zoom_level` | float | 1.0 | Current zoom factor |

Organisation: `juren` · App: `Git Sync Checker`.

### 9.4 Window Geometry Persistence

On dialog close, `save_window_geometry(key, {x,y,width,height})` writes to `config.json`.
On reopen, the saved geometry is validated against all available screens; off-screen positions are discarded and the dialog opens at the default position.

---

## 10. External Service Integrations

### 10.1 Claude Code CLI (`claude`)

**Trigger:** "Help" button per project row.

```
ClaudeResponseThread spawns:
  claude --print "<prompt>"

Prompt contents:
  - Project name and path
  - git status output
  - git log --oneline (last 5 commits)
  - Uncommitted diff (if dirty)
  - Last recorded error (if any)

Timeout: 60 s
Windows flag: CREATE_NO_WINDOW
```

Result shown in `ClaudeResponseDialog` with a copy-to-clipboard button.

### 10.2 GitHub CLI (`gh`)

**Trigger:** Edit → Scan GitHub for New Projects…

```
GitHubScanThread spawns:
  gh repo list --json nameWithOwner,pushedAt,url,latestRelease --limit 200

Filters applied in-process:
  - Exclude repos already in PROJECT_PATHS
  - Include only repos pushed to within last 7 days
  - Extract latestRelease.tagName as version string
```

Result shown in `GitHubScanDialog`: table with name, version, pushed date, and "Open on GitHub" button per row.

---

## 11. Platform Abstractions

| Concern | Windows | macOS | Linux |
|---------|---------|-------|-------|
| App icon | `app.ico` + COM `AppUserModelID` + `WM_SETICON` | `app.icns` | Multi-res PNG set |
| Subprocess console | `CREATE_NO_WINDOW` flag | — | — |
| Open terminal | Windows Terminal (`wt`) or PowerShell | Terminal.app | gnome-terminal / xterm / konsole / tilix / xfce4-terminal |
| Open file manager | `explorer.exe` | `open` | `xdg-open` |

All platform branches are guarded by `sys.platform.startswith("win")` / `"darwin"` / default-linux checks inside `IconLoader` and `MainWindow`.

The `run_git_command()` helper always uses `encoding="utf-8", errors="replace"` to prevent Windows cp1252 decoding crashes on non-ASCII commit messages.

---

## 12. Build System

### PyInstaller Spec (`git-sync-checker.spec`)

```python
a = Analysis(
    ['git_sync_checker.py'],
    datas=[
        ('resources/icons', 'resources/icons'),
        ('CHANGELOG.md', '.'),
        ('README.md', '.'),
    ],
)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name='git-sync-checker',
    console=False,
    upx=False,          # UPX corrupts Qt DLLs on Windows
    icon='resources\\icons\\app.ico',
)
```

**Build command** (must use venv pyinstaller — system Python's PyQt6 is broken):
```
venv/Scripts/pyinstaller.exe git-sync-checker.spec
```

Output: `dist/git-sync-checker.exe`
Install: `cp dist/git-sync-checker.exe ~/bin/git-sync-checker.exe`

### PowerShell Launcher (`run.ps1`)

Used for running from source. Steps:
1. Validate existing venv's Python binary is still present
2. Locate system Python (py launcher → common paths → PATH)
3. Create or recreate venv if needed
4. Activate venv
5. `pip install -r requirements.txt` if requirements.txt is newer than install marker
6. Launch `git_sync_checker.py` with pass-through arguments

---

## 13. Key Design Patterns

### Signal/Slot for Thread Safety

All background results are delivered via Qt signals, which PyQt6 automatically queues across thread boundaries:

```python
thread = GitCheckThread(paths, names)
thread.result_ready.connect(self.on_result_ready)
thread.finished.connect(self.on_finished)
thread.start()
```

No explicit mutexes or `QMutex` locking is required.

### Single-Instance Guard

```python
# Attempt to connect to existing instance
socket = QLocalSocket()
socket.connectToServer("git-sync-checker")
if socket.waitForConnected(500):
    socket.write(b"raise")   # tell existing instance to raise its window
    sys.exit(0)

# No existing instance — become the server
instance_server = QLocalServer()
instance_server.listen("git-sync-checker")
instance_server.newConnection.connect(_on_new_instance)
```

Prevents concurrent config writes and duplicate windows.

### DocViewerDialog Fallback Chain

Used for Help › Changelog and Help › User Guide:

1. **Bundled file** — `sys._MEIPASS` (frozen exe) or `_base_dir` (source)
2. **GitHub raw URL** — `urllib.request.urlopen(timeout=10)`
3. **Plain text** — if `markdown` library is unavailable

### Theme-Aware CSS in DocViewerDialog

Background brightness is detected via `palette.color(ColorRole.Window)` and the CSS is generated accordingly (dark or light variant), making the markdown renderer consistent with the active theme.

### Zoom-Reactive UI

`ZoomManager.zoom_changed` signal is connected to:
- `MainWindow._reinit_ui()` — recalculates column widths, re-renders all rows
- `GitInfoDialog._update_font()` — updates `font-size` in monospace stylesheet

This means the entire UI responds to a single font-size change without per-widget subscriptions.

### Stash→Pull→Restore Error Branches

`GitStashSyncThread` explicitly handles four outcome paths:

| Stash | Pull | Stash Pop | Outcome |
|-------|------|-----------|---------|
| ✓ | ✓ | ✓ | Success |
| ✓ | ✓ | ✗ | Partial: pulled, stash left intact |
| ✓ | ✗ | — | Pull failed, stash pop attempted to restore |
| ✗ | — | — | Stash failed, nothing changed |

Each path is logged separately with a distinct message string.

---

## 14. Data Structures Reference

### Project Row Widget Dict

```python
{
    "name":     QPushButton,   # clickable — opens GitInfoDialog
    "version":  QLabel,
    "status":   QLabel,        # colour-coded status badge
    "count":    QLabel,        # ahead/behind count
    "sync_btn": QPushButton,
    "claude_btn": QPushButton,
}
```

### `check_git_sync()` Return Tuple

```python
(status: str, ahead: int, behind: int, dirty: bool)
```

### `GitCheckThread.result_ready` Signal Payload

```python
(name: str, status: str, ahead: int, behind: int,
 dirty: bool, stash_count: int, version: str)
```

### SyncLogger Entry

```python
{
    "event":     "sync_result" | "dirty_detected" | "dirty_conflict" | "user_action",
    "project":   str,
    "success":   bool,
    "message":   str,
    "timestamp": str,   # ISO-8601 e.g. "2026-03-28T14:23:01"
}
```

### ThemeRegistry Theme Record

```python
ThemeColors(
    background, surface, text, subtext,
    accent, warning, error, success,
    border, highlight
)

UIPalette(
    window, window_text, base, alternate_base,
    text, button, button_text, highlight, highlighted_text,
    link, tooltip_base, tooltip_text
)
```
