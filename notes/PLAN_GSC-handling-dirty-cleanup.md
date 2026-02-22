# Plan: Dirty Tree Detection, Options Dialog & Logging

## Context

`git pull --ff-only` fails silently when a repo has uncommitted local changes. git-sync-checker
currently shows a raw git error dialog and no early warning. Three features address this:

1. **Dirty tree detection** — detect uncommitted changes during the status-check phase and show a
   visual indicator in the main window.
2. **Options dialog** — when the user tries to sync a dirty+behind repo, present a dialog listing
   the dirty files and offering "Stash → Pull → Restore" or "Cancel".
3. **Persistent logging** — record sync events (successes, failures, dirty detections, user
   decisions) to `sync_history.json`; viewable via a new "History" button.

---

## Critical File

**All changes in one file:** `/home/juren/Projects/git-sync-checker/git_sync_checker.py`

---

## Implementation Steps (dependency order)

### Step 1 — Imports & constants

Add to existing imports:
```python
import datetime
from PyQt6.QtWidgets import (
    ...,
    QDialog, QDialogButtonBox, QScrollArea
)
```

Add after `CONFIG_FILE`:
```python
LOG_FILE = os.path.join(_base_dir, "sync_history.json")
MAX_LOG_ENTRIES = 200
```

---

### Step 2 — `SyncLogger` class (insert before `GitCheckThread`)

Rolling JSON log, capped at `MAX_LOG_ENTRIES`. Thread-safe for our use (no shared memory state).

```python
class SyncLogger:
    @staticmethod
    def _load() -> list:
        if not os.path.exists(LOG_FILE): return []
        try:
            with open(LOG_FILE) as f: data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception: return []

    @staticmethod
    def _save(entries: list) -> None:
        try:
            with open(LOG_FILE, "w") as f: json.dump(entries, f, indent=2)
        except Exception: pass   # must never crash the app

    @staticmethod
    def log(entry: dict) -> None:
        entries = SyncLogger._load()
        entry["timestamp"] = datetime.datetime.now().isoformat(timespec="seconds")
        entries.append(entry)
        if len(entries) > MAX_LOG_ENTRIES:
            entries = entries[-MAX_LOG_ENTRIES:]
        SyncLogger._save(entries)

    @staticmethod
    def load_all() -> list:
        return list(reversed(SyncLogger._load()))  # newest-first
```

Log entry schema:

| event | required extra keys | optional |
|---|---|---|
| `dirty_detected` | `project` | — |
| `dirty_conflict` | `project`, `dirty_files` | — |
| `user_action` | `project`, `action` (`"stash_pull_restore"` or `"cancel"`) | — |
| `sync_result` | `project`, `success`, `message` | `via_stash`, `pop_failed` |

---

### Step 3 — Update `check_git_sync` → returns 4-tuple

Add after the existing `run_git_command` calls, before the `if rc_local != 0` check:

```python
rc_dirty, dirty_out, _ = run_git_command(repo_path, "status", "--porcelain")
dirty = (rc_dirty == 0) and bool(dirty_out.strip())
```

Change every `return "...", ...` to include `dirty` as the 4th element.
Return `False` for dirty on the `"error"` path to suppress spurious UI noise.

---

### Step 4 — Update `GitCheckThread`

```python
result_ready = pyqtSignal(str, str, int, int, bool)  # add bool for dirty

def run(self):
    for path, name in zip(PROJECT_PATHS, PROJECT_NAMES):
        status, ahead, behind, dirty = check_git_sync(path)
        self.result_ready.emit(name, status, ahead, behind, dirty)
```

---

### Step 5 — New `GitStashSyncThread` class (insert after `GitSyncThread`)

Reuses same `sync_done = pyqtSignal(str, bool, str)` signature as `GitSyncThread` so
`on_sync_done` handles both without changes.

```python
class GitStashSyncThread(QThread):
    sync_done = pyqtSignal(str, bool, str)

    def __init__(self, name, path):
        super().__init__()
        self.name = name
        self.path = path

    def run(self):
        rc_s, _, err_s = run_git_command(self.path, "stash")
        if rc_s != 0:
            self.sync_done.emit(self.name, False, f"Stash failed:\n{err_s}")
            return

        rc_p, out_p, err_p = run_git_command(self.path, "pull", "--ff-only")
        pull_ok = (rc_p == 0)

        rc_o, _, err_o = run_git_command(self.path, "stash", "pop")
        pop_ok = (rc_o == 0)

        if pull_ok and pop_ok:
            msg, ok = f"Stash → Pull → Pop succeeded.\n{out_p}", True
        elif pull_ok and not pop_ok:
            msg, ok = f"Pull succeeded but stash pop failed.\n{err_o}", False
        elif not pull_ok and pop_ok:
            msg, ok = f"Pull failed (stash restored):\n{err_p}", False
        else:
            msg, ok = f"Pull failed AND stash pop failed.\n{err_p}\n{err_o}", False

        self.sync_done.emit(self.name, ok, msg)
```

---

### Step 6 — New `DirtyConflictDialog` class (insert after `GitStashSyncThread`)

Modal dialog listing dirty files; returns either `STASH_ACTION` or `CANCEL_ACTION`.

```python
class DirtyConflictDialog(QDialog):
    STASH_ACTION  = 0
    CANCEL_ACTION = 1

    def __init__(self, project_name, dirty_files, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Uncommitted Changes — {project_name}")
        self.setMinimumWidth(420)
        self._action = self.CANCEL_ACTION
        layout = QVBoxLayout(self)

        info = QLabel(f"<b>{project_name}</b> has uncommitted changes.\nChoose how to proceed:")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Scrollable file list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(180)
        fw = QWidget()
        fl = QVBoxLayout(fw)
        fl.setSpacing(2)
        for line in dirty_files:
            lbl = QLabel(f"  {line}")
            lbl.setStyleSheet("font-family: monospace; color: #fd7e14;")
            fl.addWidget(lbl)
        scroll.setWidget(fw)
        layout.addWidget(scroll)

        btn_box = QDialogButtonBox()
        btn_box.addButton("Stash → Pull → Restore", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.addButton("Cancel",                 QDialogButtonBox.ButtonRole.RejectRole)
        btn_box.accepted.connect(lambda: (setattr(self, "_action", self.STASH_ACTION), self.accept()))
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def chosen_action(self):
        return self._action
```

---

### Step 7 — New `SyncHistoryDialog` class (insert after `DirtyConflictDialog`)

Scrollable read-only log viewer; uses `SyncLogger.load_all()`.

Key structure:
- Title label
- `QScrollArea` containing one `QFrame` per log entry (timestamp + project + formatted event text)
- "Close" button
- Events formatted as human-readable one-liners with success=green, failure=red, neutral=grey

---

### Step 8 — `MainWindow` changes

**8a — `__init__`:** Add tracking dicts/lists:
```python
self._stash_threads: list[GitStashSyncThread] = []
self._dirty_state: dict[str, bool] = {}
```
Add "History" button to button layout, connected to `self.show_history_dialog`.

**8b — `on_result_ready` signature:** `(self, name, status, ahead, behind, dirty)`

Store dirty state and apply overlay:
```python
self._dirty_state[name] = dirty

# ... existing status rendering (unchanged) ...

if dirty and status != "error":
    row["status"].setText(row["status"].text() + " ⚠")
    if status == "synced":
        row["status"].setStyleSheet("color: #e6ac00;")  # orange-yellow for synced+dirty

if dirty:  # log on every refresh cycle that detects dirty
    SyncLogger.log({"project": name, "event": "dirty_detected"})
```

Sync button enablement unchanged: `row["sync_btn"].setEnabled(status == "behind")`.

**8c — `sync_project`:** Before launching `GitSyncThread`, intercept dirty state:
```python
if self._dirty_state.get(name, False):
    rc, out, _ = run_git_command(path, "status", "--porcelain")  # fresh at click time
    dirty_files = [l for l in out.splitlines() if l.strip()] if rc == 0 else []
    if dirty_files:
        SyncLogger.log({"project": name, "event": "dirty_conflict", "dirty_files": dirty_files})
        dlg = DirtyConflictDialog(name, dirty_files, parent=self)
        dlg.exec()
        if dlg.chosen_action() == DirtyConflictDialog.CANCEL_ACTION:
            SyncLogger.log({"project": name, "event": "user_action", "action": "cancel"})
            return
        SyncLogger.log({"project": name, "event": "user_action", "action": "stash_pull_restore"})
        row["sync_btn"].setEnabled(False)
        row["status"].setText("⏳ Stashing...")
        row["status"].setStyleSheet("")
        row["count"].setText("")
        thread = GitStashSyncThread(name, path)
        thread.sync_done.connect(self.on_sync_done)
        thread.start()
        self._stash_threads.append(thread)
        return
    # else: dirty state was stale — fall through to normal sync
```

**8d — `on_sync_done`:** Log result; on success, trigger a re-check of that single project
(so dirty state and counts are accurate) rather than setting labels directly:
```python
SyncLogger.log({"project": name, "event": "sync_result", "success": success, "message": message})
if success:
    self._dirty_state[name] = False
    row["status"].setText("⏳ Checking...")
    row["status"].setStyleSheet("")
    # Launch GitSingleCheckThread (new lightweight QThread, see below) for this project
else:
    row["status"].setText("❌ Sync failed")
    row["status"].setStyleSheet("color: #888888;")
    row["sync_btn"].setEnabled(True)
    QMessageBox.warning(self, "Sync Failed", f"{name}:\n{message}")
```

**`GitSingleCheckThread`** (minimal new class): runs `check_git_sync` for one project, emits
`result_ready` with the same signature as `GitCheckThread` so `on_result_ready` handles it
identically. No changes to `on_result_ready` needed.

**8e — Add `show_history_dialog` method:**
```python
def show_history_dialog(self):
    SyncHistoryDialog(parent=self).exec()
```

---

## User-Confirmed Design Decisions

- **Dirty log frequency:** Log `dirty_detected` on every refresh cycle that finds dirty files
  (not just on first detection). Produces a richer history.
- **Post-sync refresh:** After a successful sync, auto re-run a single-project status check
  so the UI reflects the true post-sync state (counts, dirty flag) rather than assuming success.

---

## Verification

1. **Clean repo refresh** — "✓ In Sync" with no ⚠, Sync button disabled.
2. **Behind repo** — "↓ Behind", Sync enabled, clean pull logs `sync_result:success=true`.
3. **Dirty synced repo** — modify tracked file; refresh; "✓ In Sync ⚠" in orange-yellow.
4. **Dirty behind repo** — "↓ Behind ⚠"; click Sync → dialog with file list appears.
   - Cancel → nothing changes; log has `user_action:cancel`.
   - Stash+Pull+Restore → re-check runs; status shows true post-sync state; log has full chain.
5. **Stale dirty state** — check shows dirty; user reverts manually; click Sync → no dialog shown.
6. **History button** — events appear newest-first with green/red/grey coloring.
7. **Pop failure** — stash pop conflict shows explicit warning about pop failure.
