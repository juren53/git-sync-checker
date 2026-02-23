# Git Sync Checker (GSC)

A PyQt6 desktop application that monitors whether your local git repositories are in sync with their remotes. Add any number of projects, see at a glance which ones need attention, and sync them with a single click.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- **Multi-repo monitoring** — track any number of local git repositories from a single window
- **Color-coded status** — instantly see which repos are synced, ahead, behind, or diverged
- **One-click sync** — pull behind repos with a single button press (`git pull --ff-only`)
- **Dirty tree handling** — detects uncommitted changes and offers Stash → Pull → Restore workflow
- **Git Info drill-down** — click any project name to open a dialog with 10 tabs covering every angle of a repo: overview strip, latest commit stat, full diff patch, unstaged changes, working-tree status, stash list, remotes, branches, tags, repo config, and an ASCII branch graph
- **Get Help (Claude Code)** — ask Claude Code for diagnosis and fix suggestions on problematic repos
- **Sync history log** — persistent event log (sync attempts, dirty detections, user actions) viewable via History dialog
- **Zoom in/out** — scale the UI via View menu (`Ctrl++` / `Ctrl+-` / `Ctrl+0`) or `Ctrl+Mouse Wheel`; zoom level persists across sessions
- **Theme support** — five built-in themes (Dark, Light, Solarized Light, Dracula, GitHub) selectable via Edit > Preferences
- **Auto-refresh** — optional timed re-check interval, configurable in Preferences
- **Desktop integration** — `.desktop` file and XDG icon installation for Linux system menus

## Status Indicators

| Symbol | Meaning | Color |
|--------|---------|-------|
| ✓ In Sync | Local and remote are identical | Green |
| ↑ Ahead | Local has unpushed commits | Blue |
| ↓ Behind | Remote has new commits (Sync enabled) | Orange |
| ⇅ Diverged | Both sides have different commits | Red |
| ⚠ | Uncommitted local changes detected | Yellow |
| ❌ Error | Could not check repo (missing, no remote, etc.) | Grey |

## Installation

### Run from source

```bash
git clone https://github.com/juren53/git-sync-checker.git
cd git-sync-checker
./run.sh
```

`run.sh` will create a virtual environment, install dependencies, and launch the app.

### Build a standalone binary

Requires [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller git-sync-checker.spec
```

The compiled binary is written to `dist/git-sync-checker`. To install it:

```bash
cp dist/git-sync-checker ~/.local/bin/
```

### Desktop menu entry (Linux)

Copy the `.desktop` file and install the icon:

```bash
cp git-sync-checker.desktop ~/.local/share/applications/
```

Icons are installed to the XDG hicolor theme at standard sizes (16–256px) from `resources/icons/`.

## Usage

Launch the app from the system menu or from the terminal:

```bash
python git_sync_checker.py        # from source
git-sync-checker                  # compiled binary
```

### Adding and removing projects

- Click **Add Project** and select any local git repository directory.
- Click **Remove** on a project row to stop tracking it.
- Projects are stored in `config.json` alongside the application.

### Syncing a behind repo

When a repo is behind its remote, the **Sync** button activates. Clicking it runs `git pull --ff-only`.

If the repo has uncommitted changes (⚠), a dialog offers:
- **Stash → Pull → Restore** — stashes changes, pulls, then pops the stash
- **Cancel** — abort the sync

### Viewing git details for a project

Click the **project name** (underlined) in any row to open the Git Info dialog for that repo. It shows:

- **Overview** — current branch, upstream tracking branch, HEAD short SHA, and remote origin URL
- **Latest Commit tab** — `git show --stat HEAD`: commit hash, author, date, message, and per-file change summary
- **Log (last 20) tab** — recent history in a columnar format: short hash, relative date, author, and subject
- **Git Show tab** — full `git show HEAD` patch output with file headers, `@@` hunks, and added/removed lines
- **Git Diff tab** — unstaged working-tree changes (`git diff`); shows `(no unstaged changes)` when the tree is clean
- **Git Status tab** — full `git status` output: branch tracking info, staged changes, unstaged changes, and untracked files
- **Git Stash tab** — stash entries (`git stash list`); shows `(no stashes)` when the stash is empty
- **Git Remote tab** — all configured remotes with fetch and push URLs (`git remote -v`)
- **Git Branches tab** — all local and remote-tracking branches with short SHA, tracking relationship, and latest commit subject (`git branch -a -vv`)
- **Git Tags tab** — all tags with their one-line annotation or commit message (`git tag -n`); shows `(no tags)` when none exist
- **Git Config tab** — repo-level configuration settings from `.git/config` (`git config --local --list`)
- **Git Log tab** — ASCII branch graph of the full repo history across all branches (`git log --oneline --graph --decorate --all`)

Use **Refresh** inside the dialog to re-query git without closing it.

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl++` or `Ctrl+=` | Zoom in |
| `Ctrl+-` | Zoom out |
| `Ctrl+0` | Reset zoom to 100% |
| `Ctrl+Mouse Wheel` | Zoom in/out |

### Menu bar

- **File** — Exit
- **Edit** — Preferences (auto-refresh interval, auto-check on launch, theme)
- **View** — Zoom In, Zoom Out, Reset Zoom
- **Help** — Changelog, User Guide, About

## Configuration

All settings are stored in `config.json` in the application directory:

- **projects** — list of tracked repository paths
- **preferences** — auto-refresh interval (minutes, 0 = off), auto-check on launch, theme name

Zoom level is stored separately via Qt's `QSettings`.

## Requirements

- Python 3.8+
- PyQt6 >= 6.5.0
- Git (accessible on `PATH`)
- [pyqt-app-info](https://github.com/juren53/pyqt-app-info) — About dialog support
- [zoom-manager](https://github.com/juren53/zoom-manager) — UI zoom/font scaling
- Optional: [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`claude`) for the Get Help feature

## License

MIT
