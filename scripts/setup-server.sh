#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────
# Strava Leaderboard Bot — Server Provisioning Script
# Run ONCE on the remote server as root.
# Creates the deploy user, directories, clones repos,
# sets up SSH keys, and prepares for CI/CD.
# ─────────────────────────────────────────────────────────

DEPLOY_USER="strava-leaderboard"
DEPLOY_HOME="/home/${DEPLOY_USER}"

echo "=== Creating deploy user: ${DEPLOY_USER} ==="
if id "${DEPLOY_USER}" &>/dev/null; then
    echo "User already exists — skipping creation."
else
    useradd --create-home --shell /bin/bash "${DEPLOY_USER}"
    echo "User created."
fi

echo "=== Setting up SSH for CI/CD deploy ==="
DEPLOY_SSH_DIR="${DEPLOY_HOME}/.ssh"
mkdir -p "${DEPLOY_SSH_DIR}"
chmod 700 "${DEPLOY_SSH_DIR}"

# Paste the CI/CD deploy public key here
# (Generate on your local machine via: ssh-keygen -t ed25519 -C "ci-deploy@strava-leaderboard-bot")
# Then add the public key to this file:
cat > "${DEPLOY_SSH_DIR}/authorized_keys" << 'KEYS'
# CI/CD Deploy Key (GitHub Actions → server)
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM9Cyvxv3u7ASYzrZA0cZXJu7qqSQ4E54bkk5XDSY9uk ci-deploy@strava-leaderboard-bot
KEYS

chmod 600 "${DEPLOY_SSH_DIR}/authorized_keys"
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${DEPLOY_SSH_DIR}"
echo "SSH authorized_keys set up."

echo "=== Creating deployment directories ==="
mkdir -p /opt/strava-leaderboard-bot/{stage,prod}
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" /opt/strava-leaderboard-bot
echo "Directories created at /opt/strava-leaderboard-bot/{stage,prod}"

echo "=== Cloning repository into staging ==="
cd /opt/strava-leaderboard-bot/stage
if [ -d .git ]; then
    echo "Git repo already exists — pulling latest."
    git pull origin develop
else
    sudo -u "${DEPLOY_USER}" git clone https://github.com/natalka1122/strava-leaderboard-bot.git .
    sudo -u "${DEPLOY_USER}" git checkout develop
fi

echo "=== Cloning repository into production ==="
cd /opt/strava-leaderboard-bot/prod
if [ -d .git ]; then
    echo "Git repo already exists — pulling latest."
    sudo -u "${DEPLOY_USER}" git pull origin main
else
    sudo -u "${DEPLOY_USER}" git clone https://github.com/natalka1122/strava-leaderboard-bot.git .
    sudo -u "${DEPLOY_USER}" git checkout main
fi

# Switch remotes to HTTPS for password-free pulls
for dir in stage prod; do
    cd "/opt/strava-leaderboard-bot/${dir}"
    sudo -u "${DEPLOY_USER}" git remote set-url origin https://github.com/natalka1122/strava-leaderboard-bot.git
done
echo "Git remotes switched to HTTPS (no auth needed for public repo)."

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                     SETUP COMPLETE                          ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                             ║"
echo "║  NEXT STEPS:                                                ║"
echo "║                                                             ║"
echo "║  1. Create .env files:                                      ║"
echo "║     /opt/strava-leaderboard-bot/stage/.env                  ║"
echo "║     /opt/strava-leaderboard-bot/prod/.env                   ║"
echo "║                                                             ║"
echo "║  2. On GitHub, add these repository secrets:                ║"
echo "║     DEPLOY_HOST → 138.199.201.181                           ║"
echo "║     DEPLOY_USER → strava-leaderboard                        ║"
echo "║     DEPLOY_SSH_KEY → (private key from generation step)     ║"
echo "║                                                             ║"
echo "║  3. On GitHub, enable branch protection:                    ║"
echo "║     Settings → Branches → Add rule                          ║"
echo "║     • develop: Require PR, require approval                 ║"
echo "║     • main:    Require PR from develop, require approval    ║"
echo "║                                                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"