#!/bin/bash
DESKTOP_FILE="$HOME/.local/share/applications/git-sync-checker.desktop"
COMPILED="Exec=/home/juren/.local/bin/git-sync-checker"
PYTHON="Exec=python3 /home/juren/Projects/git-sync-checker/git_sync_checker.py"

if grep -q "^Exec=python3" "$DESKTOP_FILE"; then
    sed -i "s|^Exec=.*|$COMPILED|" "$DESKTOP_FILE"
    echo "Switched to COMPILED version"
else
    sed -i "s|^Exec=.*|$PYTHON|" "$DESKTOP_FILE"
    echo "Switched to PYTHON version"
fi
