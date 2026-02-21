# Git Sync Checker

A PyQt6 desktop application that checks if local git repositories are in sync with their GitHub remotes.

## Features

- Monitor sync status of multiple git repositories
- Shows ahead/behind commit counts
- Color-coded status indicators:
  - Green: In sync with remote
  - Blue: Ahead of remote (local commits not pushed)
  - Orange: Behind remote (remote has new commits)
  - Red: Diverged (both have different commits)
- Refresh on demand via button click

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python git_sync_checker.py
```

## Requirements

- Python 3.8+
- PyQt6

## Projects Monitored

- HST-Metadata
- MDviewer
- JAUs-Systems
- tag-writer
- system-monitor

## License

MIT
