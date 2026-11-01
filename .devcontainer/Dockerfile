FROM mcr.microsoft.com/devcontainers/base:ubuntu26.04

ENV DEBIAN_FRONTEND=noninteractive
# System packages + Python
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        curl \
        gnupg \
        python3 \
        python3-pip \
        python3-venv \
        gh \
        fd-find \
        ripgrep \
        wl-clipboard && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    chmod 644 /etc/apt/keyrings/nodesource.gpg && \
    printf 'Types: deb\nURIs: https://deb.nodesource.com/node_24.x/\nSuites: nodistro\nComponents: main\nSigned-By: /etc/apt/keyrings/nodesource.gpg\n' > /etc/apt/sources.list.d/nodesource.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs ffmpeg && \
    npm install -g agent-browser @tobilu/qmd && \
    npm cache clean --force && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*


# `python` alias = plain symlink to python3 — no python-is-python3 package, so
# no alternatives re-registration can ever flip the default away from 3.14.
RUN ln -sf /usr/bin/python3 /usr/bin/python

# `fd-find` installs its binary as `fdfind` on Debian/Ubuntu (the `fd` name
# collides with an unrelated package), but upstream docs and muscle memory both
# say `fd`. Alias it so either name works.
RUN ln -sf /usr/bin/fdfind /usr/bin/fd

# Fresh pip: distro pip is deb-managed (no RECORD file) and refuses normal
# `--upgrade` uninstall. `--ignore-installed` skips the uninstall step; the new
# pip lands first on sys.path (/usr/local/lib/python3.14/dist-packages) and wins.
RUN python3 -m pip install --ignore-installed --break-system-packages pip

# uv is the installer for the dev toolchain below, so bootstrap it with pip
# first (it cannot install itself from the group it reads).
RUN python3 -m pip install --no-cache-dir --break-system-packages uv

# App runtime deps — the same file the production image installs (repo-root
# Dockerfile). Without these `pytest` cannot even import the app modules, so
# tests/mypy are unrunnable in the devcontainer.
COPY app/requirements.txt /tmp/requirements.txt
RUN uv pip install --system --break-system-packages --no-cache \
        -r /tmp/requirements.txt && \
    rm -f /tmp/requirements.txt

# Python tooling — versions/deps declared once in pyproject.toml
# ([dependency-groups].dev), not here. Copied rather than bind-mounted so the
# layer invalidates whenever the group changes.
COPY pyproject.toml /tmp/pyproject.toml
RUN cd /tmp && \
    uv pip install --system --break-system-packages --no-cache --group dev && \
    rm -f /tmp/pyproject.toml

# Pi Coding Agent + agent-browser runtime — user scope, installed AS `vscode`.
ARG PI_VERSION=v1.4.0

USER vscode
RUN npm install -g --ignore-scripts --prefix "$HOME/.local" @earendil-works/pi-coding-agent@${PI_VERSION} && \
    agent-browser install --with-deps && \
    npm cache clean --force && \
    sudo rm -rf /var/lib/apt/lists/*
