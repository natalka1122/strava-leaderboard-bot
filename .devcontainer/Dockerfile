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
        ripgrep && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    chmod 644 /etc/apt/keyrings/nodesource.gpg && \
    printf 'Types: deb\nURIs: https://deb.nodesource.com/node_24.x/\nSuites: nodistro\nComponents: main\nSigned-By: /etc/apt/keyrings/nodesource.gpg\n' > /etc/apt/sources.list.d/nodesource.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs ffmpeg && \
    npm install -g agent-browser && \
    npm cache clean --force && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*


# `python` alias = plain symlink to python3 — no python-is-python3 package, so
# no alternatives re-registration can ever flip the default away from 3.14.
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Fresh pip: distro pip is deb-managed (no RECORD file) and refuses normal
# `--upgrade` uninstall. `--ignore-installed` skips the uninstall step; the new
# pip lands first on sys.path (/usr/local/lib/python3.14/dist-packages) and wins.
RUN python3 -m pip install --ignore-installed --break-system-packages pip

# Python tooling
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    argcomplete \
    mypy \
    pytest \
    pytest-cov \
    pytest-asyncio \
    black \
    wemake-python-styleguide \
    cohesion \
    dlint \
    pytest-xdist \
    vulture \
    isort \
    jupyter \
    pipenv \
    uv \
    openai

# Pi Coding Agent + agent-browser runtime — user scope, installed AS `vscode`.
ARG PI_VERSION=v0.87.1

USER vscode
RUN npm install -g --ignore-scripts --prefix "$HOME/.local" @earendil-works/pi-coding-agent@${PI_VERSION} && \
    agent-browser install --with-deps && \
    npm cache clean --force && \
    sudo rm -rf /var/lib/apt/lists/*
