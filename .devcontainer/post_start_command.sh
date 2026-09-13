#!/usr/bin/env bash
set -e

git config --global user.email "${GIT_AUTHOR_EMAIL:?set GIT_AUTHOR_EMAIL in local env}"
git config --global user.name "${GIT_AUTHOR_NAME:?set GIT_AUTHOR_NAME in local env}"

# Fix SSH permissions
sudo chown -R vscode:vscode ~/.ssh || true
chmod 700 ~/.ssh || true
chmod 600 ~/.ssh/* || true

# Fix gh permissions (credential mount)
sudo chown -R vscode:vscode ~/.config/gh 2>/dev/null || true

# Fix npm cache permissions (defensive fix)
sudo chown -R vscode:vscode ~/.npm 2>/dev/null || true

# warmup line so the caches are hot before you first open pi (hopefully)
pi --help >/dev/null 2>&1
