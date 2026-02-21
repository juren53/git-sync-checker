#!/bin/bash

# This script automates the setup and execution of the Git Sync Checker application.

# It first checks for the existence of a Python virtual environment in the '.venv'
# directory. If the environment doesn't exist, it creates one and installs all the
# necessary dependencies listed in the 'requirements.txt' file.

# After ensuring the environment is ready, it launches the application.

# Navigate to the script's directory
cd "$(dirname "$0")"

# Activate virtual environment
# Check if the virtual environment directory exists
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
  echo "Installing dependencies..."
  .venv/bin/pip install -r requirements.txt
fi

echo "Starting Git Sync Checker..."
.venv/bin/python git_sync_checker.py