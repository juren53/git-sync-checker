import sys
import os
import subprocess
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFrame, QMessageBox, QFileDialog)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from typing import Any, Optional
from PyQt6.QtGui import QFont

__version__ = "0.0.3"


CONFIG_FILE = "config.json"


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
    rc_remote, remote_head, _ = run_git_command(repo_path, "rev-parse", "@{u}")
    rc_ahead, ahead_out, _ = run_git_command(repo_path, "rev-list", "--count", "@{u}..HEAD")
    rc_behind, behind_out, _ = run_git_command(repo_path, "rev-list", "--count", "HEAD..@{u}")

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
        self._initialize_project_ui()

        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.start_check)
        button_layout.addWidget(self.refresh_btn)

        self.add_project_btn = QPushButton("Add Project")
        self.add_project_btn.clicked.connect(self.add_project_dialog)
        button_layout.addWidget(self.add_project_btn)

        main_layout.addLayout(button_layout)

        self.git_thread: Optional[QThread] = None

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

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.delete_project(name))
        layout.addWidget(delete_btn)

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


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.start_check()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
