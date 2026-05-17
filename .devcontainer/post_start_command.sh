#!/usr/bin/env bash
set -e

git config --global user.email "natalka1122@gmail.com"
git config --global user.name "natalka1122"

# Fix SSH permissions
sudo chown -R vscode:vscode ~/.ssh || true
chmod 700 ~/.ssh || true
chmod 600 ~/.ssh/* || true

# Restore pi agent sessions
ln -s /workspaces/strava/.pi/sessions /home/vscode/.pi/agent/sessions
