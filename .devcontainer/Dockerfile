FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

ENV DEBIAN_FRONTEND=noninteractive
# System packages + Python
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        software-properties-common \
        git \
        curl \
        iputils-ping \
        net-tools \
        telnet \
        tcpdump \
        redis-tools \
        netcat-openbsd \
        dnsutils \
        gh \
        fd-find \
        ripgrep && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.14 \
        python3.14-venv \
        python3-pip \
        python-is-python3 && \
    rm -rf /var/lib/apt/lists/*

# Make Python 3.14 default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.14 1

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

# Node.js 22 + Pi Coding Agent
ARG PI_VERSION=v0.85.1
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g --ignore-scripts @earendil-works/pi-coding-agent@${PI_VERSION} && \
    npm cache clean --force && \
    rm -rf /var/lib/apt/lists/*

# Base pi settings (defaults only - no packages; they are registered below)
COPY .devcontainer/settings.json /home/vscode/.pi/agent/settings.json

# Install pi packages: pi appends each source to the `packages` array in the
# file copied above. HOME=/home/vscode is required because the build runs as root.
RUN HOME=/home/vscode pi install npm:pi-mcp-adapter && \
    HOME=/home/vscode pi install npm:pi-matt-pocock-skills && \
    HOME=/home/vscode pi install npm:@dietrichgebert/ponytail && \
    HOME=/home/vscode pi install npm:pi-web-access && \
    HOME=/home/vscode pi install npm:pi-hermes-memory && \
    HOME=/home/vscode pi install git:github.com/jonjonrankin/pi-caveman

ARG MY_OPENROUTER_API_KEY
ENV MY_OPENROUTER_API_KEY=${MY_OPENROUTER_API_KEY}
COPY .devcontainer/auth.json.tpl /home/vscode/.pi/agent/auth.json.tpl
RUN envsubst < /home/vscode/.pi/agent/auth.json.tpl > /home/vscode/.pi/agent/auth.json && \
    chown -R vscode:vscode /home/vscode/.pi /home/vscode/.npm && \
    chmod 600 /home/vscode/.pi/agent/auth.json
