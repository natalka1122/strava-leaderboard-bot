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
        gh && \
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
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g @mariozechner/pi-coding-agent && \
    npm cache clean --force && \
    rm -rf /var/lib/apt/lists/*
RUN pi update

ARG MY_OPENROUTER_API_KEY
ENV MY_OPENROUTER_API_KEY=${MY_OPENROUTER_API_KEY}
COPY .devcontainer/auth.json.tpl /home/vscode/.pi/agent/auth.json.tpl
COPY .devcontainer/models.json /home/vscode/.pi/agent/models.json
RUN envsubst < /home/vscode/.pi/agent/auth.json.tpl > /home/vscode/.pi/agent/auth.json && \
    chown -R vscode:vscode /home/vscode/.pi && \
    chmod 600 /home/vscode/.pi/agent/auth.json
