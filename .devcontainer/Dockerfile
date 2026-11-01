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

# Python deps (app runtime + the pyproject dev group) are deliberately NOT
# installed here. They go into a repo-local .venv at container-create time —
# see .devcontainer/setup_python_env.sh and the postCreateCommand. A project
# venv is what pi-lens, pyright, VS Code and the tests all resolve to;
# installing system-wide left them with no detectable interpreter and
# type-checking against one that lacked the app deps.

# Pi Coding Agent + agent-browser runtime — user scope, installed AS `vscode`.
ARG PI_VERSION=v1.4.0

USER vscode
RUN npm install -g --ignore-scripts --prefix "$HOME/.local" @earendil-works/pi-coding-agent@${PI_VERSION} && \
    agent-browser install --with-deps && \
    npm cache clean --force && \
    sudo rm -rf /var/lib/apt/lists/*
