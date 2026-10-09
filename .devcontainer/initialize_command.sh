#!/usr/bin/env bash
# Host-side init, runs *outside* the container (initializeCommand):
#  - writes canonical pi settings (model + packages) over the gitignored
#    workspace .pi/, which is bind-mounted into the container. Canonical wins
#    on every start — runtime tweaks to .pi/agent/settings.json are reverted.
#  - writes pi auth.json from the local OpenRouter key, so the key never
#    enters container env vars, process environ, or image layers.
set -euo pipefail

# The bind mount sources this var at container-create time, *before* this
# script runs. If it's unset, Docker fails with a cryptic mount error.
# Fail here, loudly, instead.
if [ -z "${GITHUB_SSH_DIR:-}" ]; then
    echo "ERROR: GITHUB_SSH_DIR is unset (host env)." >&2
    echo "Export it before opening the devcontainer, e.g.:" >&2
    echo "  export GITHUB_SSH_DIR=\$HOME/.ssh" >&2
    exit 1
fi
if [ ! -d "${GITHUB_SSH_DIR}" ]; then
    echo "ERROR: GITHUB_SSH_DIR points to a missing dir: ${GITHUB_SSH_DIR}" >&2
    exit 1
fi

# 1. Seed pi settings from versioned canonical (recreate-safe, canonical wins)
SETTINGS_IN="${SETTINGS_IN:-.devcontainer/pi-settings.json}"
SETTINGS_OUT="${SETTINGS_OUT:-.pi/agent/settings.json}"
mkdir -p "$(dirname "${SETTINGS_OUT}")"
cp "${SETTINGS_IN}" "${SETTINGS_OUT}"
echo "wrote canonical settings to ${SETTINGS_OUT}"

# 2. Pre-create the workspace-local gh config dir AND the pi sessions dir
#    (both are bind-mount sources): a missing dir would make Docker fabricate a
#    root-owned one that blocks vscode writes. Empty = valid first-run state,
#    so no fail-loud here (unlike SSH).
mkdir -p .config/gh .pi/agent/sessions

# 3. Auth
umask 177
KEY="${MY_OPENROUTER_API_KEY:-}"
OUT="${AUTH_OUT:-.pi/agent/auth.json}"

# Never clobber a working key with an empty one (e.g. env var briefly unset),
# and never write a placeholder empty key (pi would error at startup trying to
# use ""). Only write auth.json when we actually have a key.
if [ -z "${KEY}" ]; then
    if [ -f "${OUT}" ] && grep -q '"key": "..' "${OUT}"; then
        echo "WARN: MY_OPENROUTER_API_KEY unset; keeping existing ${OUT}" >&2
    else
        echo "WARN: MY_OPENROUTER_API_KEY unset and no existing ${OUT}; skipping write" >&2
    fi
else
    mkdir -p "$(dirname "$OUT")"
    cat > "$OUT" <<EOF
{
  "openrouter": {
    "type": "api_key",
    "key": "${KEY}"
  }
}
EOF
    chmod 600 "$OUT"
    echo "wrote $OUT"
fi

echo "Wait for container build"
