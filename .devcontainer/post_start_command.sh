#!/usr/bin/env bash
set -e

if [ -z "${GIT_AUTHOR_EMAIL:-}" ] || [ -z "${GIT_AUTHOR_NAME:-}" ]; then
    echo "WARN: GIT_AUTHOR_EMAIL/GIT_AUTHOR_NAME unset; skipping git identity setup" >&2
else
    git config --global user.email "${GIT_AUTHOR_EMAIL}"
    git config --global user.name "${GIT_AUTHOR_NAME}"
fi

# Fix SSH permissions (credential mount)
sudo chown -R vscode:vscode ~/.ssh || true
chmod 700 ~/.ssh 2>/dev/null || true
chmod 600 ~/.ssh/id_* ~/.ssh/*_ed25519 2>/dev/null || true
chmod 644 ~/.ssh/known_hosts ~/.ssh/config 2>/dev/null || true

# Fix gh permissions (credential mount)
sudo chown -R vscode:vscode ~/.config/gh 2>/dev/null || true

# Fix PI permissions
sudo chown -R vscode:vscode  ~/.pi 2>/dev/null || true

# Refresh declared pi packages only
if command -v pi >/dev/null 2>&1; then
    if ! UPDATE_OUT=$(GIT_TERMINAL_PROMPT=0 pi update --extensions 2>&1); then
        echo "WARN: pi update --extensions failed:" >&2
        echo "${UPDATE_OUT}" >&2
    fi
fi

# Install pre-commit git hooks (config + versioned in repo). Idempotent: re-runs
# on every container start, so hooks survive re-clones/rebase and re-install
# after .git/hooks is wiped. All hooks are `language: system` (tools already on
# PATH via the pyproject dev group), so no environment build is needed.
if command -v pre-commit >/dev/null 2>&1; then
    if ! PRE_COMMIT_OUT=$(pre-commit install 2>&1); then
        echo "WARN: pre-commit install failed:" >&2
        echo "${PRE_COMMIT_OUT}" >&2
    fi
else
    echo "WARN: pre-commit not found; skipping hook install" >&2
fi
