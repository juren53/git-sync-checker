import sys
import os
import subprocess
import json
import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFrame, QMessageBox, QFileDialog,
                             QDialog, QDialogButtonBox, QScrollArea, QTextEdit,
                             QSpinBox, QCheckBox, QFormLayout, QComboBox, QGridLayout, QTabWidget,
                             QLineEdit)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from typing import Any, Optional
from PyQt6.QtGui import QFont, QFontMetrics, QIcon, QAction
from icon_loader import icons
from zoom_manager import ZoomManager
from pyqt_app_info import AppIdentity, gather_info
from pyqt_app_info.qt import AboutDialog
from theme_manager import get_theme_registry, get_fusion_palette

__version__ = "0.4.5"


if getattr(sys, 'frozen', False):
    _base_dir = os.path.dirname(sys.executable)
else:
    _base_dir = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(_base_dir, "config.json")
LOG_FILE = os.path.join(_base_dir, "sync_history.json")
MAX_LOG_ENTRIES = 200


def load_projects():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({"projects": []}, f)
        return [], []

    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
        paths = [os.path.expanduser(p) for p in data.get("projects", [])]
        names = [os.path.basename(p) for p in paths]
        return paths, names

def save_projects(paths):
    data = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
    home_dir = os.path.expanduser("~")
    data["projects"] = [p.replace(home_dir, "~") for p in paths]
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


_DEFAULT_PREFS = {"auto_refresh_interval": 0, "auto_check_on_launch": True, "theme": "dark"}


def load_preferences():
    if not os.path.exists(CONFIG_FILE):
        return dict(_DEFAULT_PREFS)
    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
    prefs = dict(_DEFAULT_PREFS)
    prefs.update(data.get("preferences", {}))
    return prefs


def save_preferences(prefs):
    data = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
    data["preferences"] = prefs
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


PROJECT_PATHS, PROJECT_NAMES = load_projects()


class SyncLogger:
    @staticmethod
    def _load() -> list:
        if not os.path.exists(LOG_FILE):
            return []
        try:
            with open(LOG_FILE) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @staticmethod
    def _save(entries: list) -> None:
        try:
            with open(LOG_FILE, "w") as f:
                json.dump(entries, f, indent=2)
        except Exception:
            pass  # must never crash the app

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


class GitCheckThread(QThread):
    result_ready = pyqtSignal(str, str, int, int, bool, int)  # name, status, ahead, behind, dirty, stash_count

    def run(self):
        for path, name in zip(PROJECT_PATHS, PROJECT_NAMES):
            status, ahead, behind, dirty = check_git_sync(path)
            rc_st, stash_out, _ = run_git_command(path, "stash", "list")
            stash_count = len([l for l in stash_out.splitlines() if l.strip()]) if rc_st == 0 else 0
            self.result_ready.emit(name, status, ahead, behind, dirty, stash_count)


class GitSyncThread(QThread):
    sync_done = pyqtSignal(str, bool, str)  # name, success, message

    def __init__(self, name, path):
        super().__init__()
        self.name = name
        self.path = path

    def run(self):
        rc, out, err = run_git_command(self.path, "pull", "--ff-only")
        success = rc == 0
        self.sync_done.emit(self.name, success, out if success else err)


class GitStashSyncThread(QThread):
    sync_done = pyqtSignal(str, bool, str)  # name, success, message

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
            msg, ok = f"Stash \u2192 Pull \u2192 Pop succeeded.\n{out_p}", True
        elif pull_ok and not pop_ok:
            msg, ok = f"Pull succeeded but stash pop failed.\n{err_o}", False
        elif not pull_ok and pop_ok:
            msg, ok = f"Pull failed (stash restored):\n{err_p}", False
        else:
            msg, ok = f"Pull failed AND stash pop failed.\n{err_p}\n{err_o}", False

        self.sync_done.emit(self.name, ok, msg)


class ClaudeResponseThread(QThread):
    response_ready = pyqtSignal(str, bool, str)  # name, success, response

    def __init__(self, name, path, prompt):
        super().__init__()
        self.name = name
        self.path = path
        self.prompt = prompt

    def run(self):
        try:
            kwargs = {}
            if sys.platform.startswith("win"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(
                ["claude", "--print", self.prompt],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=60,
                **kwargs
            )
            if result.returncode == 0:
                self.response_ready.emit(self.name, True, result.stdout.strip())
            else:
                self.response_ready.emit(self.name, False,
                    result.stderr.strip() or "Claude returned a non-zero exit code.")
        except FileNotFoundError:
            self.response_ready.emit(self.name, False,
                "Claude Code CLI not found. Is `claude` installed and on your PATH?")
        except subprocess.TimeoutExpired:
            self.response_ready.emit(self.name, False,
                "Request timed out after 60 seconds.")
        except Exception as e:
            self.response_ready.emit(self.name, False, str(e))


def run_git_command(repo_path, *args):
    try:
        kwargs = {}
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            **kwargs
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return -1, "", str(e)


def check_git_sync(repo_path):
    if not os.path.isdir(repo_path):
        return "error", 0, 0, False

    run_git_command(repo_path, "fetch", "--all")

    rc_local, local_head, _ = run_git_command(repo_path, "rev-parse", "HEAD")
    rc_remote, remote_head, _ = run_git_command(repo_path, "rev-parse", "@{u}")
    rc_ahead, ahead_out, _ = run_git_command(repo_path, "rev-list", "--count", "@{u}..HEAD")
    rc_behind, behind_out, _ = run_git_command(repo_path, "rev-list", "--count", "HEAD..@{u}")

    if rc_local != 0 or rc_remote != 0:
        return "error", 0, 0, False

    rc_dirty, dirty_out, _ = run_git_command(repo_path, "status", "--porcelain")
    dirty = (rc_dirty == 0) and bool(dirty_out.strip())

    if local_head == remote_head:
        return "synced", 0, 0, dirty

    try:
        ahead = int(ahead_out) if rc_ahead == 0 else 0
        behind = int(behind_out) if rc_behind == 0 else 0
    except (ValueError, TypeError):
        ahead, behind = 0, 0

    if ahead > 0 and behind > 0:
        return "diverged", ahead, behind, dirty
    elif ahead > 0:
        return "ahead", ahead, behind, dirty
    elif behind > 0:
        return "behind", ahead, behind, dirty
    else:
        return "unknown", 0, 0, dirty


class DirtyConflictDialog(QDialog):
    STASH_ACTION  = 0
    CANCEL_ACTION = 1

    def __init__(self, project_name, dirty_files, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Uncommitted Changes \u2014 {project_name}")
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
        btn_box.addButton("Stash \u2192 Pull \u2192 Restore", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.addButton("Cancel",                           QDialogButtonBox.ButtonRole.RejectRole)
        btn_box.accepted.connect(lambda: (setattr(self, "_action", self.STASH_ACTION), self.accept()))
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def chosen_action(self):
        return self._action


class SyncHistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sync History")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        layout = QVBoxLayout(self)

        title = QLabel("Sync History (newest first)")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(4)

        entries = SyncLogger.load_all()
        if not entries:
            container_layout.addWidget(QLabel("No history yet."))
        else:
            for entry in entries:
                frame = QFrame()
                frame.setFrameShape(QFrame.Shape.StyledPanel)
                frame_layout = QVBoxLayout(frame)
                frame_layout.setContentsMargins(6, 4, 6, 4)

                event = entry.get("event", "unknown")
                project = entry.get("project", "?")
                timestamp = entry.get("timestamp", "")

                text, color = self._format_entry(entry, event)

                top_line = QLabel(f"<b>{timestamp}</b> \u2014 {project}")
                top_line.setStyleSheet("color: #aaaaaa; font-size: 11px;")
                frame_layout.addWidget(top_line)

                detail = QLabel(text)
                detail.setStyleSheet(f"color: {color};")
                detail.setWordWrap(True)
                frame_layout.addWidget(detail)

                container_layout.addWidget(frame)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _format_entry(self, entry, event):
        if event == "dirty_detected":
            return "Dirty tree detected", "#e6ac00"
        elif event == "dirty_conflict":
            files = entry.get("dirty_files", [])
            return f"Dirty conflict \u2014 {len(files)} file(s) uncommitted", "#fd7e14"
        elif event == "user_action":
            action = entry.get("action", "unknown")
            if action == "stash_pull_restore":
                return "User chose: Stash \u2192 Pull \u2192 Restore", "#007bff"
            else:
                return "User chose: Cancel", "#888888"
        elif event == "sync_result":
            success = entry.get("success", False)
            message = entry.get("message", "")
            via_stash = entry.get("via_stash", False)
            prefix = "(via stash) " if via_stash else ""
            if success:
                return f"{prefix}Sync succeeded", "#28a745"
            else:
                first_line = message.split("\n")[0] if message else "Unknown error"
                return f"{prefix}Sync failed: {first_line}", "#dc3545"
        else:
            return f"Event: {event}", "#888888"


class GitInfoDialog(QDialog):
    """Drill-down dialog showing git show / git log for a project."""

    def __init__(self, project_name, project_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Git Info — {project_name}")
        self.setMinimumSize(620, 520)
        self._name = project_name
        self._path = project_path

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ── Overview strip ────────────────────────────────────────
        ov_frame = QFrame()
        ov_frame.setFrameShape(QFrame.Shape.StyledPanel)
        ov_grid = QGridLayout(ov_frame)
        ov_grid.setContentsMargins(8, 6, 8, 6)
        ov_grid.setHorizontalSpacing(12)

        self._lbl_branch   = QLabel()
        self._lbl_tracking = QLabel()
        self._lbl_head     = QLabel()
        self._lbl_head.setStyleSheet("font-family: monospace;")
        self._lbl_url      = QLabel()
        self._lbl_url.setStyleSheet("font-family: monospace; font-size: 11px;")
        self._lbl_url.setWordWrap(True)

        ov_grid.addWidget(QLabel("<b>Branch:</b>"),   0, 0)
        ov_grid.addWidget(self._lbl_branch,           0, 1)
        ov_grid.addWidget(QLabel("<b>Tracking:</b>"), 0, 2)
        ov_grid.addWidget(self._lbl_tracking,         0, 3)
        ov_grid.addWidget(QLabel("<b>HEAD:</b>"),     1, 0)
        ov_grid.addWidget(self._lbl_head,             1, 1)
        ov_grid.addWidget(QLabel("<b>URL:</b>"),      1, 2)
        ov_grid.addWidget(self._lbl_url,              1, 3)
        ov_grid.setColumnStretch(3, 1)
        layout.addWidget(ov_frame)

        # ── Tabs ──────────────────────────────────────────────────
        self._tabs = QTabWidget()

        self._show_edit = QTextEdit()
        self._show_edit.setReadOnly(True)
        self._show_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._tabs.addTab(self._show_edit, "Latest Commit")

        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._tabs.addTab(self._log_edit, "Log (last 20)")

        self._gitshow_edit = QTextEdit()
        self._gitshow_edit.setReadOnly(True)
        self._gitshow_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._tabs.addTab(self._gitshow_edit, "Git Show")

        self._diff_edit = QTextEdit()
        self._diff_edit.setReadOnly(True)
        self._diff_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._tabs.addTab(self._diff_edit, "Git Diff")

        self._status_edit = QTextEdit()
        self._status_edit.setReadOnly(True)
        self._status_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._tabs.addTab(self._status_edit, "Git Status")

        self._stash_edit = QTextEdit()
        self._stash_edit.setReadOnly(True)
        self._stash_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._tabs.addTab(self._stash_edit, "Git Stash")

        self._remote_edit = QTextEdit()
        self._remote_edit.setReadOnly(True)
        self._remote_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._tabs.addTab(self._remote_edit, "Git Remote")

        self._branches_edit = QTextEdit()
        self._branches_edit.setReadOnly(True)
        self._branches_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._tabs.addTab(self._branches_edit, "Git Branches")

        self._tags_edit = QTextEdit()
        self._tags_edit.setReadOnly(True)
        self._tags_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._tabs.addTab(self._tags_edit, "Git Tags")

        self._config_edit = QTextEdit()
        self._config_edit.setReadOnly(True)
        self._config_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._tabs.addTab(self._config_edit, "Git Config")

        self._gitlog_edit = QTextEdit()
        self._gitlog_edit.setReadOnly(True)
        self._gitlog_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._tabs.addTab(self._gitlog_edit, "Git Log")

        blame_widget = QWidget()
        blame_layout = QVBoxLayout(blame_widget)
        blame_layout.setContentsMargins(4, 4, 4, 4)
        blame_layout.setSpacing(4)
        input_row = QHBoxLayout()
        self._blame_input = QLineEdit()
        self._blame_input.setPlaceholderText("Relative file path…")
        self._blame_input.setStyleSheet("font-family: monospace;")
        self._blame_input.returnPressed.connect(self._run_blame)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_blame_file)
        show_btn = QPushButton("Show")
        show_btn.clicked.connect(self._run_blame)
        input_row.addWidget(self._blame_input)
        input_row.addWidget(browse_btn)
        input_row.addWidget(show_btn)
        self._blame_edit = QTextEdit()
        self._blame_edit.setReadOnly(True)
        self._blame_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        blame_layout.addLayout(input_row)
        blame_layout.addWidget(self._blame_edit)
        self._tabs.addTab(blame_widget, "Git Blame")

        grep_widget = QWidget()
        grep_layout = QVBoxLayout(grep_widget)
        grep_layout.setContentsMargins(4, 4, 4, 4)
        grep_layout.setSpacing(4)
        grep_row = QHBoxLayout()
        self._grep_pattern = QLineEdit()
        self._grep_pattern.setPlaceholderText("Search pattern…")
        self._grep_pattern.returnPressed.connect(self._run_grep)
        self._grep_glob = QLineEdit()
        self._grep_glob.setPlaceholderText("File glob (e.g. *.py) — optional")
        self._grep_glob.setFixedWidth(200)
        grep_btn = QPushButton("Search")
        grep_btn.clicked.connect(self._run_grep)
        grep_row.addWidget(self._grep_pattern)
        grep_row.addWidget(self._grep_glob)
        grep_row.addWidget(grep_btn)
        self._grep_edit = QTextEdit()
        self._grep_edit.setReadOnly(True)
        self._grep_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        grep_layout.addLayout(grep_row)
        grep_layout.addWidget(self._grep_edit)
        self._tabs.addTab(grep_widget, "Git Grep")

        self._shortlog_edit = QTextEdit()
        self._shortlog_edit.setReadOnly(True)
        self._shortlog_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._tabs.addTab(self._shortlog_edit, "Git Shortlog")

        layout.addWidget(self._tabs)

        # ── Buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._populate)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._populate()

    # ── helpers ──────────────────────────────────────────────────

    def _git(self, *args):
        rc, out, _ = run_git_command(self._path, *args)
        return out.strip() if rc == 0 else ""

    def _git_text(self, *args):
        rc, out, err = run_git_command(self._path, *args)
        return out if rc == 0 else f"(error: {err})"

    def _populate(self):
        branch   = self._git("branch", "--show-current") or "(detached HEAD)"
        tracking = self._git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") or "(none)"
        head_sha = self._git("rev-parse", "--short", "HEAD") or "?"
        url      = self._git("remote", "get-url", "origin") or "(no remote)"

        self._lbl_branch.setText(branch)
        self._lbl_tracking.setText(tracking)
        self._lbl_head.setText(head_sha)
        self._lbl_url.setText(url)

        self._show_edit.setPlainText(self._git_text("show", "--stat", "HEAD"))
        self._gitshow_edit.setPlainText(self._git_text("show", "HEAD"))
        diff_out = self._git_text("diff")
        self._diff_edit.setPlainText(diff_out if diff_out.strip() else "(no unstaged changes)")
        self._status_edit.setPlainText(self._git_text("status"))
        stash_out = self._git_text("stash", "list")
        self._stash_edit.setPlainText(stash_out if stash_out.strip() else "(no stashes)")
        self._remote_edit.setPlainText(self._git_text("remote", "-v"))
        self._branches_edit.setPlainText(self._git_text("branch", "-a", "-vv"))
        tags_out = self._git_text("tag", "-n")
        self._tags_edit.setPlainText(tags_out if tags_out.strip() else "(no tags)")
        self._config_edit.setPlainText(self._git_text("config", "--local", "--list"))
        self._gitlog_edit.setPlainText(
            self._git_text("log", "--oneline", "--graph", "--decorate", "--all")
        )
        self._shortlog_edit.setPlainText(self._git_text("shortlog", "-sne", "--all"))
        first_file = self._git(
            "diff-tree", "--no-commit-id", "-r", "--name-only", "HEAD"
        ).splitlines()
        if first_file and not self._blame_input.text():
            self._blame_input.setText(first_file[0])
        self._log_edit.setPlainText(
            self._git_text(
                "log",
                "--pretty=format:%h  %<(14,trunc)%ar  %<(20,trunc)%an  %s",
                "-20",
            )
        )

    def _browse_blame_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File for Blame", self._path)
        if path:
            rel = os.path.relpath(path, self._path).replace("\\", "/")
            self._blame_input.setText(rel)
            self._run_blame()

    def _run_blame(self):
        filepath = self._blame_input.text().strip()
        if not filepath:
            self._blame_edit.setPlainText("Enter a file path above and click Show.")
            return
        out = self._git_text("blame", filepath)
        self._blame_edit.setPlainText(out if out.strip() else f"(no blame output for '{filepath}')")

    def _run_grep(self):
        pattern = self._grep_pattern.text().strip()
        if not pattern:
            self._grep_edit.setPlainText("Enter a search pattern above and click Search.")
            return
        args = ["grep", "-n", "--heading", pattern]
        glob = self._grep_glob.text().strip()
        if glob:
            args += ["--", glob]
        out = self._git_text(*args)
        self._grep_edit.setPlainText(out if out.strip() else f"(no matches for '{pattern}')")


class ClaudeResponseDialog(QDialog):
    def __init__(self, project_name, response, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Claude's Suggestion — {project_name}")
        self.setMinimumWidth(540)
        self.setMinimumHeight(400)
        layout = QVBoxLayout(self)

        title = QLabel(f"Claude's suggestion for <b>{project_name}</b>:")
        title.setWordWrap(True)
        layout.addWidget(title)

        text_area = QTextEdit()
        text_area.setReadOnly(True)
        text_area.setPlainText(response)
        text_area.setStyleSheet("font-family: monospace; font-size: 12px;")
        layout.addWidget(text_area)

        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(response))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)


class PreferencesDialog(QDialog):
    def __init__(self, prefs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.auto_refresh_spin = QSpinBox()
        self.auto_refresh_spin.setRange(0, 120)
        self.auto_refresh_spin.setValue(prefs.get("auto_refresh_interval", 0))
        self.auto_refresh_spin.setSpecialValueText("Disabled")
        self.auto_refresh_spin.setSuffix(" min")
        form.addRow("Auto-refresh interval:", self.auto_refresh_spin)

        self.auto_check_cb = QCheckBox()
        self.auto_check_cb.setChecked(prefs.get("auto_check_on_launch", True))
        form.addRow("Auto-check on launch:", self.auto_check_cb)

        self.theme_combo = QComboBox()
        registry = get_theme_registry()
        self._theme_names = []
        for name, theme in registry.get_all_themes().items():
            self._theme_names.append(name)
            self.theme_combo.addItem(theme.display_name)
        current_theme = prefs.get("theme", "dark")
        if current_theme in self._theme_names:
            self.theme_combo.setCurrentIndex(self._theme_names.index(current_theme))
        form.addRow("Theme:", self.theme_combo)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_preferences(self):
        return {
            "auto_refresh_interval": self.auto_refresh_spin.value(),
            "auto_check_on_launch": self.auto_check_cb.isChecked(),
            "theme": self._theme_names[self.theme_combo.currentIndex()],
        }


def _show_text_file_dialog(parent, title, file_path):
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumSize(620, 520)
    layout = QVBoxLayout(dlg)
    text_area = QTextEdit()
    text_area.setReadOnly(True)
    text_area.setStyleSheet("font-family: monospace; font-size: 12px;")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text_area.setPlainText(f.read())
    except Exception as e:
        text_area.setPlainText(f"Could not load file:\n{e}")
    layout.addWidget(text_area)
    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dlg.accept)
    layout.addWidget(close_btn)
    dlg.exec()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Git Sync Checker v{__version__}")
        self.setMinimumSize(500, 300)
        self.setWindowIcon(icons.app_icon())
        self._setup_menu_bar()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        header = QLabel("Project Sync Status")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        main_layout.addWidget(header)

        self.status_frame = QFrame()
        self.status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.status_layout = QGridLayout(self.status_frame)
        self.status_layout.setHorizontalSpacing(10)
        self.status_layout.setColumnStretch(1, 1)
        main_layout.addWidget(self.status_frame)

        self.project_widgets: dict[str, dict[str, Any]] = {}
        self._initialize_project_ui()

        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.start_check)
        button_layout.addWidget(self.refresh_btn)

        self.add_project_btn = QPushButton("Add Project")
        self.add_project_btn.clicked.connect(self.add_project_dialog)
        button_layout.addWidget(self.add_project_btn)

        self.history_btn = QPushButton("History")
        self.history_btn.clicked.connect(self.show_history_dialog)
        button_layout.addWidget(self.history_btn)

        main_layout.addLayout(button_layout)

        self.git_thread: Optional[QThread] = None
        self._sync_threads: list[GitSyncThread] = []
        self._stash_threads: list[GitStashSyncThread] = []
        self._claude_threads: list[ClaudeResponseThread] = []
        self._dirty_state: dict[str, bool] = {}

        self._prefs = load_preferences()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.start_check)
        self._apply_auto_refresh()
        self._apply_theme()

        self.zoom_manager = ZoomManager.instance()
        self.zoom_manager.zoom_changed.connect(self._on_zoom_changed)

    def _clear_project_ui(self):
        while self.status_layout.count():
            item = self.status_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.project_widgets.clear()


    def _initialize_project_ui(self):
        self._clear_project_ui()
        fm = QFontMetrics(QApplication.instance().font())
        max_name_width = max((fm.horizontalAdvance(n) for n in PROJECT_NAMES), default=80) + 20
        for i, name in enumerate(PROJECT_NAMES):
            row = self.create_project_row(name, max_name_width)
            self.project_widgets[name] = row
            for col, widget in enumerate(row["widgets"]):
                self.status_layout.addWidget(widget, i, col)


    def create_project_row(self, name, name_width):
        name_label = QPushButton(name)
        name_label.setFlat(True)
        name_label.setCursor(Qt.CursorShape.PointingHandCursor)
        name_label.setToolTip(f"Click to view git details for {name}")
        name_label.setStyleSheet("text-align: left; padding: 2px 0px; text-decoration: underline;")
        name_label.setFixedWidth(name_width)
        name_label.clicked.connect(lambda: self.show_git_info(name))

        status_label = QLabel("⏳ Checking...")

        count_label = QLabel("")
        count_label.setFixedWidth(60)

        sync_btn = QPushButton("Sync")
        sync_btn.setEnabled(False)
        sync_btn.clicked.connect(lambda: self.sync_project(name))

        claude_btn = QPushButton("Get Help")
        claude_btn.clicked.connect(lambda: self.ask_claude(name))

        delete_btn = QPushButton("Remove")
        delete_btn.clicked.connect(lambda: self.delete_project(name))

        widgets = [name_label, status_label, count_label, sync_btn, claude_btn, delete_btn]
        row = {"widgets": widgets, "name": name_label, "status": status_label, "count": count_label, "sync_btn": sync_btn, "claude_btn": claude_btn}
        return row

    def start_check(self):
        self.refresh_btn.setEnabled(False)
        for row in self.project_widgets.values():
            row["status"].setText("⏳ Checking...")
            row["status"].setStyleSheet("")
            row["count"].setText("")

        self.git_thread = GitCheckThread()
        self.git_thread.result_ready.connect(self.on_result_ready)
        self.git_thread.finished.connect(self.on_finished)
        self.git_thread.start()

    def on_result_ready(self, name, status, ahead, behind, dirty, stash_count):
        row = self.project_widgets[name]
        self._dirty_state[name] = dirty

        row["status"].setToolTip("")

        if status == "error":
            row["status"].setText("❌ Error")
            row["status"].setStyleSheet("color: #888888;")
        elif status == "synced":
            row["status"].setText("✓ In Sync")
            row["status"].setStyleSheet("color: #28a745;")
        elif status == "ahead":
            row["status"].setText("↑ Ahead")
            row["status"].setStyleSheet("color: #007bff;")
            row["count"].setText(f"+{ahead}")
        elif status == "behind":
            row["status"].setText("↓ Behind")
            row["status"].setStyleSheet("color: #fd7e14;")
            row["count"].setText(f"-{behind}")
        elif status == "diverged":
            row["status"].setText("⇅ Diverged")
            row["status"].setStyleSheet("color: #dc3545;")
            row["count"].setText(f"+{ahead} -{behind}")

        if dirty and status != "error":
            row["status"].setText(row["status"].text() + " \u26a0")
            if status == "synced":
                row["status"].setStyleSheet("color: #e6ac00;")

        if dirty:
            SyncLogger.log({"event": "dirty_detected", "project": name})

        if stash_count > 0:
            row["status"].setText(row["status"].text() + " 📦")
            stash_tip = f"{stash_count} stash(es) found — may be a leftover from a failed sync.\nOpen Git Info > Stash tab to review."
            existing_tip = row["status"].toolTip()
            row["status"].setToolTip((existing_tip + "\n" + stash_tip).strip() if existing_tip else stash_tip)

        row["sync_btn"].setEnabled(status == "behind")

    def on_finished(self):
        self.refresh_btn.setEnabled(True)

    def sync_project(self, name):
        idx = PROJECT_NAMES.index(name)
        path = PROJECT_PATHS[idx]
        row = self.project_widgets[name]

        if self._dirty_state.get(name, False):
            rc, out, _ = run_git_command(path, "status", "--porcelain")
            dirty_files = [l for l in out.splitlines() if l.strip()] if rc == 0 else []
            if dirty_files:
                SyncLogger.log({"event": "dirty_conflict", "project": name, "dirty_files": dirty_files})
                dlg = DirtyConflictDialog(name, dirty_files, parent=self)
                dlg.exec()
                if dlg.chosen_action() == DirtyConflictDialog.CANCEL_ACTION:
                    SyncLogger.log({"event": "user_action", "project": name, "action": "cancel"})
                    return
                SyncLogger.log({"event": "user_action", "project": name, "action": "stash_pull_restore"})
                row["sync_btn"].setEnabled(False)
                row["status"].setText("\u23f3 Stashing...")
                row["status"].setStyleSheet("")
                row["count"].setText("")
                thread = GitStashSyncThread(name, path)
                thread.sync_done.connect(self.on_sync_done)
                thread.start()
                self._stash_threads.append(thread)
                return

        row["sync_btn"].setEnabled(False)
        row["status"].setText("⏳ Syncing...")
        row["status"].setStyleSheet("")
        row["count"].setText("")

        thread = GitSyncThread(name, path)
        thread.sync_done.connect(self.on_sync_done)
        thread.start()
        self._sync_threads.append(thread)

    def on_sync_done(self, name, success, message):
        row = self.project_widgets[name]
        SyncLogger.log({"event": "sync_result", "project": name, "success": success, "message": message})
        if success:
            self._dirty_state[name] = False
            row["status"].setText("⏳ Checking...")
            row["status"].setStyleSheet("")
            self.start_check()
        else:
            row["status"].setText("❌ Sync failed — ask Claude Code?")
            row["status"].setStyleSheet("color: #888888;")
            row["status"].setToolTip(message)
            row["sync_btn"].setEnabled(True)
            QMessageBox.warning(self, "Sync Failed",
                                f"{name}:\n{message}\n\nTip: ask Claude Code to help fix this.")

    def ask_claude(self, name):
        idx = PROJECT_NAMES.index(name)
        path = PROJECT_PATHS[idx]
        row = self.project_widgets[name]

        status_text = row["status"].text()
        error_msg   = row["status"].toolTip()
        dirty       = self._dirty_state.get(name, False)

        _, status_out, _ = run_git_command(path, "status")
        _, log_out,    _ = run_git_command(path, "log", "--oneline", "-5")

        dirty_section = ""
        if dirty:
            _, porcelain, _ = run_git_command(path, "status", "--porcelain")
            dirty_section = f"\nUncommitted changes:\n{porcelain}"

        error_section = f"\nLast error:\n{error_msg}" if error_msg else ""

        prompt = (
            f"I'm using git-sync-checker to monitor git repos.\n\n"
            f"Project: {name}\nPath: {path}\nStatus: {status_text}"
            f"{error_section}{dirty_section}\n\n"
            f"Git status:\n{status_out}\n\n"
            f"Recent commits:\n{log_out}\n\n"
            f"Please diagnose this git issue and suggest clear, practical steps to fix it."
        )

        row["claude_btn"].setEnabled(False)
        row["claude_btn"].setText("⏳ Asking...")

        thread = ClaudeResponseThread(name, path, prompt)
        thread.response_ready.connect(self.on_claude_response)
        thread.start()
        self._claude_threads.append(thread)

    def on_claude_response(self, name, success, response):
        row = self.project_widgets[name]
        row["claude_btn"].setEnabled(True)
        row["claude_btn"].setText("Get Help")
        if success:
            ClaudeResponseDialog(name, response, parent=self).exec()
        else:
            QMessageBox.warning(self, "Claude Error",
                                f"Could not get a response:\n{response}")

    def add_project_dialog(self):
        # Use QFileDialog to get a directory
        directory = QFileDialog.getExistingDirectory(self, "Select Project Directory")

        if directory:
            # Check if directory is already in PROJECT_PATHS (after expanding user path)
            expanded_current_paths = [os.path.realpath(os.path.expanduser(p)) for p in PROJECT_PATHS]
            expanded_new_path = os.path.realpath(os.path.expanduser(directory))

            if expanded_new_path in expanded_current_paths:
                QMessageBox.warning(self, "Duplicate Project", "This project is already in the list.")
                return

            # Add the new project path to PROJECT_PATHS and PROJECT_NAMES
            # Ensure the path is stored consistently (e.g., as a user-relative path if applicable)
            PROJECT_PATHS.append(directory)
            PROJECT_NAMES.append(os.path.basename(directory))

            # Save the updated project list
            save_projects(PROJECT_PATHS)

            # Refresh the UI
            self._initialize_project_ui()

            # Optionally, start checking the new project immediately
            self.start_check()

    def delete_project(self, name):
        reply = QMessageBox.question(self, "Remove Project",
                                     f"Are you sure you want to remove project '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            global PROJECT_PATHS, PROJECT_NAMES
            try:
                # Find the index of the project to delete
                index_to_delete = PROJECT_NAMES.index(name)

                # Remove from both lists
                PROJECT_PATHS.pop(index_to_delete)
                PROJECT_NAMES.pop(index_to_delete)

                # Save the updated project list
                # Note: save_projects expects a list of paths as currently stored in PROJECT_PATHS,
                # which are relative paths like "~/Projects/..."
                save_projects(PROJECT_PATHS)

                # Refresh the UI
                self._initialize_project_ui()

                QMessageBox.information(self, "Project Removed", f"Project '{name}' has been removed.")
            except ValueError:
                QMessageBox.warning(self, "Error", f"Project '{name}' not found.")

    def show_history_dialog(self):
        SyncHistoryDialog(parent=self).exec()

    def show_git_info(self, name):
        idx = PROJECT_NAMES.index(name)
        GitInfoDialog(name, PROJECT_PATHS[idx], parent=self).exec()

    # ------------------------------------------------------------------ menu

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        # File
        file_menu = menu_bar.addMenu("&File")
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit
        edit_menu = menu_bar.addMenu("&Edit")
        prefs_action = QAction("&Preferences", self)
        prefs_action.triggered.connect(self._action_preferences)
        edit_menu.addAction(prefs_action)

        # View
        view_menu = menu_bar.addMenu("&View")

        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(self._zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_in_alt = QAction(self)
        zoom_in_alt.setShortcut("Ctrl+=")
        zoom_in_alt.triggered.connect(self._zoom_in)
        self.addAction(zoom_in_alt)

        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(self._zoom_out)
        view_menu.addAction(zoom_out_action)

        view_menu.addSeparator()
        zoom_reset_action = QAction("&Reset Zoom", self)
        zoom_reset_action.setShortcut("Ctrl+0")
        zoom_reset_action.triggered.connect(self._zoom_reset)
        view_menu.addAction(zoom_reset_action)

        # Help
        help_menu = menu_bar.addMenu("&Help")
        changelog_action = QAction("&Changelog", self)
        changelog_action.triggered.connect(self._action_changelog)
        help_menu.addAction(changelog_action)
        userguide_action = QAction("&User Guide", self)
        userguide_action.triggered.connect(self._action_user_guide)
        help_menu.addAction(userguide_action)
        help_menu.addSeparator()
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._action_about)
        help_menu.addAction(about_action)

    def _apply_auto_refresh(self):
        self._refresh_timer.stop()
        interval_min = self._prefs.get("auto_refresh_interval", 0)
        if interval_min > 0:
            self._refresh_timer.start(interval_min * 60 * 1000)

    def _apply_theme(self):
        theme_name = self._prefs.get("theme", "dark")
        palette = get_fusion_palette(theme_name)
        QApplication.instance().setPalette(palette)

    def _action_preferences(self):
        dlg = PreferencesDialog(self._prefs, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._prefs = dlg.get_preferences()
            save_preferences(self._prefs)
            self._apply_auto_refresh()
            self._apply_theme()

    def _action_changelog(self):
        changelog_path = os.path.join(_base_dir, "CHANGELOG.md")
        QDesktopServices.openUrl(QUrl.fromLocalFile(changelog_path))

    def _action_user_guide(self):
        readme_path = os.path.join(_base_dir, "README.md")
        QDesktopServices.openUrl(QUrl.fromLocalFile(readme_path))

    def _zoom_in(self):
        app = QApplication.instance()
        self.zoom_manager.zoom_in(app)

    def _zoom_out(self):
        app = QApplication.instance()
        self.zoom_manager.zoom_out(app)

    def _zoom_reset(self):
        app = QApplication.instance()
        self.zoom_manager.reset_zoom(app)

    def _on_zoom_changed(self, factor: float):
        self._initialize_project_ui()
        zoom_pct = self.zoom_manager.get_zoom_percentage()
        self.statusBar().showMessage(f"Zoom: {zoom_pct}%", 2000)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            app = QApplication.instance()
            if event.angleDelta().y() > 0:
                self.zoom_manager.zoom_in(app)
            elif event.angleDelta().y() < 0:
                self.zoom_manager.zoom_out(app)
            event.accept()
        else:
            super().wheelEvent(event)

    def closeEvent(self, event):
        app = QApplication.instance()
        self.zoom_manager.save_zoom_preference(app)
        event.accept()

    def _action_about(self):
        identity = AppIdentity(
            name="Git Sync Checker",
            short_name="GSC",
            version=__version__,
            description="A PyQt6 desktop app that monitors git repository sync status.",
            features=[
                "Monitor multiple git repositories",
                "Sync behind repos with one click",
                "Stash \u2192 Pull \u2192 Restore for dirty repos",
                "Get Help via Claude Code integration",
                "Persistent sync history log",
            ],
        )
        info = gather_info(identity, caller_file=__file__)
        dlg = AboutDialog(info, parent=self)
        font = dlg.font()
        font.setPointSize(int(font.pointSize() * 1.15))
        dlg.setFont(font)
        dlg.exec()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setOrganizationName("juren")
    app.setApplicationName("Git Sync Checker")
    app.setDesktopFileName("git-sync-checker")
    app.setWindowIcon(icons.app_icon())

    zoom_mgr = ZoomManager.instance()
    zoom_mgr.initialize_base_font(app)
    zoom_mgr.apply_saved_zoom(app)

    window = MainWindow()
    window.show()
    icons.set_taskbar_icon(window, app_id="com.juren.git-sync-checker")
    if window._prefs.get("auto_check_on_launch", True):
        window.start_check()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
