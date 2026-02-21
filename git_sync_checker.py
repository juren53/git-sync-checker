import sys
import os
import subprocess
import json
import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFrame, QMessageBox, QFileDialog,
                             QDialog, QDialogButtonBox, QScrollArea)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from typing import Any, Optional
from PyQt6.QtGui import QFont, QIcon
from icon_loader import icons

__version__ = "0.2.1"


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
    with open(CONFIG_FILE, "w") as f:
        # Storing with ~ for cross-platform friendliness
        home_dir = os.path.expanduser("~")
        project_paths_to_save = [p.replace(home_dir, "~") for p in paths]
        json.dump({"projects": project_paths_to_save}, f, indent=4)


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
    result_ready = pyqtSignal(str, str, int, int, bool)  # name, status, ahead, behind, dirty

    def run(self):
        for path, name in zip(PROJECT_PATHS, PROJECT_NAMES):
            status, ahead, behind, dirty = check_git_sync(path)
            self.result_ready.emit(name, status, ahead, behind, dirty)


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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Git Sync Checker v{__version__}")
        self.setMinimumSize(500, 300)
        self.setWindowIcon(icons.app_icon())

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        header = QLabel("Project Sync Status")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        main_layout.addWidget(header)

        self.status_frame = QFrame()
        self.status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.status_layout = QVBoxLayout(self.status_frame)
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
        self._dirty_state: dict[str, bool] = {}

    def _clear_project_ui(self):
        # Remove all widgets from self.status_layout
        while self.status_layout.count():
            item = self.status_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Recursively clear sub-layouts
                self._clear_layout_widgets(item.layout())
                item.layout().deleteLater()
        self.project_widgets.clear()

    def _clear_layout_widgets(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout_widgets(item.layout())
                item.layout().deleteLater()


    def _initialize_project_ui(self):
        self._clear_project_ui() # Clear existing UI elements first
        for name in PROJECT_NAMES:
            row = self.create_project_row(name)
            self.project_widgets[name] = row
            self.status_layout.addLayout(row["layout"])


    def create_project_row(self, name):
        layout = QHBoxLayout()

        name_label = QLabel(name)
        name_label.setMinimumWidth(150)
        layout.addWidget(name_label)

        status_label = QLabel("⏳ Checking...")
        status_label.setMinimumWidth(100)
        layout.addWidget(status_label)

        count_label = QLabel("")
        count_label.setMinimumWidth(80)
        layout.addWidget(count_label)

        sync_btn = QPushButton("Sync")
        sync_btn.setEnabled(False)
        sync_btn.clicked.connect(lambda: self.sync_project(name))
        layout.addWidget(sync_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.delete_project(name))
        layout.addWidget(delete_btn)

        row = {"layout": layout, "name": name_label, "status": status_label, "count": count_label, "sync_btn": sync_btn}
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

    def on_result_ready(self, name, status, ahead, behind, dirty):
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
        reply = QMessageBox.question(self, "Delete Project",
                                     f"Are you sure you want to delete project '{name}'?",
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

                QMessageBox.information(self, "Project Deleted", f"Project '{name}' has been deleted.")
            except ValueError:
                QMessageBox.warning(self, "Error", f"Project '{name}' not found.")

    def show_history_dialog(self):
        SyncHistoryDialog(parent=self).exec()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Git Sync Checker")
    app.setDesktopFileName("git-sync-checker")
    app.setWindowIcon(icons.app_icon())
    window = MainWindow()
    window.show()
    icons.set_taskbar_icon(window, app_id="com.juren.git-sync-checker")
    window.start_check()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
