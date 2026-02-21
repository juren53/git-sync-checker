import sys
import os
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFrame, QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from typing import Any, Optional
from PyQt6.QtGui import QFont

__version__ = "0.0.2"


PROJECT_NAMES = ["HST-Metadata", "MDviewer", "JAUs-Systems", "tag-writer", "system-monitor"]
HOME_DIR = os.path.expanduser("~")
PROJECTS_DIR = os.path.join(HOME_DIR, "Projects")
PROJECT_PATHS = [os.path.join(PROJECTS_DIR, name) for name in PROJECT_NAMES]


class GitCheckThread(QThread):
    result_ready = pyqtSignal(str, str, int, int)

    def run(self):
        for path, name in zip(PROJECT_PATHS, PROJECT_NAMES):
            status, ahead, behind = check_git_sync(path)
            self.result_ready.emit(name, status, ahead, behind)


def run_git_command(repo_path, *args):
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return -1, "", str(e)


def check_git_sync(repo_path):
    if not os.path.isdir(repo_path):
        return "error", 0, 0

    run_git_command(repo_path, "fetch", "--all")

    rc_local, local_head, _ = run_git_command(repo_path, "rev-parse", "HEAD")
    rc_remote, remote_head, _ = run_git_command(repo_path, "rev-parse", "origin/HEAD")
    rc_ahead, ahead_out, _ = run_git_command(repo_path, "rev-list", "--count", "origin/HEAD..HEAD")
    rc_behind, behind_out, _ = run_git_command(repo_path, "rev-list", "--count", "HEAD..origin/HEAD")

    if rc_local != 0 or rc_remote != 0:
        return "error", 0, 0

    if local_head == remote_head:
        return "synced", 0, 0

    try:
        ahead = int(ahead_out) if rc_ahead == 0 else 0
        behind = int(behind_out) if rc_behind == 0 else 0
    except (ValueError, TypeError):
        ahead, behind = 0, 0

    if ahead > 0 and behind > 0:
        return "diverged", ahead, behind
    elif ahead > 0:
        return "ahead", ahead, behind
    elif behind > 0:
        return "behind", ahead, behind
    else:
        return "unknown", 0, 0


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Git Sync Checker v{__version__}")
        self.setMinimumSize(500, 300)

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
        for name in PROJECT_NAMES:
            row = self.create_project_row(name)
            self.project_widgets[name] = row
            self.status_layout.addLayout(row["layout"])

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.start_check)
        main_layout.addWidget(self.refresh_btn)

        self.git_thread: Optional[QThread] = None

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

        row = {"layout": layout, "name": name_label, "status": status_label, "count": count_label}
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

    def on_result_ready(self, name, status, ahead, behind):
        row = self.project_widgets[name]

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

    def on_finished(self):
        self.refresh_btn.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.start_check()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
