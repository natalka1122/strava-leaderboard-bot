#!/usr/bin/env bash
# Create/sync the repo-local Python virtualenv that pi-lens, pyright, VS Code
# and the tests all resolve to.
#
# Why a venv instead of `--system`: pi-lens (and the editor tooling) detect a
# project interpreter via .venv / VIRTUAL_ENV, and pyright type-checks against
# whatever interpreter it launches. With deps installed system-wide there was no
# detectable environment, so pyright fell back to a PATH interpreter without the
# app deps and emitted spurious `reportMissingModuleSource` for `requests`.
#
# Runs from `postCreateCommand`, i.e. once per container create/rebuild, with
# the workspace already mounted. .venv lives in the bind-mounted workspace, so
# it survives restarts. Re-run this by hand after editing app/requirements.txt
# or the pyproject dev group without rebuilding.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

# --allow-existing: a rebuild reuses the .venv already in the bind mount.
uv venv --allow-existing .venv
uv pip install --python .venv/bin/python -r app/requirements.txt --group dev

echo "Python env ready: $(.venv/bin/python --version) at ${REPO_ROOT}/.venv"
