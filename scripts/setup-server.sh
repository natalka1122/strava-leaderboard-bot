#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────
# Strava Leaderboard Bot — Server Provisioning Script
#
# Run ONCE PER ENVIRONMENT on the target server, as root:
#
#   sudo ./setup-server.sh stage   # staging, tracks develop
#   sudo ./setup-server.sh prod    # production, tracks main
#
# Stage and prod may live on the same server (run the script
# twice, once per environment) or on two different servers
# (run it once on each). Each environment gets its own
# deploy SSH key and its own checkout.
# ─────────────────────────────────────────────────────────

REPO_OWNER="natalka1122"
REPO_NAME="strava-leaderboard-bot"
REPO_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"
DEPLOY_USER="strava-leaderboard"
DEPLOY_HOME="/home/${DEPLOY_USER}"
DEPLOY_ROOT="/opt/${REPO_NAME}"
GH_ENVS_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/settings/environments"

usage() {
    echo "Usage: sudo $0 <stage|prod>" >&2
    exit 1
}

ENV_NAME="${1:-}"
case "${ENV_NAME}" in
    stage) BRANCH="develop" ;;
    prod)  BRANCH="main" ;;
    *)     usage ;;
esac

if [ "${EUID}" -ne 0 ]; then
    echo "ERROR: this script must be run as root." >&2
    usage
fi

TARGET_DIR="${DEPLOY_ROOT}/${ENV_NAME}"

echo ""
echo "=== Strava Leaderboard Bot — server setup: ${ENV_NAME} (branch: ${BRANCH}) ==="

# ── Deploy user ──────────────────────────────────────────
echo ""
echo "=== Creating deploy user: ${DEPLOY_USER} ==="
if id "${DEPLOY_USER}" &>/dev/null; then
    echo "  ✓ User already exists."
else
    useradd --create-home --shell /bin/bash "${DEPLOY_USER}"
    echo "  ✓ Created."
fi

# ── SSH deploy key (one per environment) ─────────────────
echo ""
echo "=== Setting up CI deploy key for '${ENV_NAME}' ==="
DEPLOY_SSH_DIR="${DEPLOY_HOME}/.ssh"
mkdir -p "${DEPLOY_SSH_DIR}"
chmod 700 "${DEPLOY_SSH_DIR}"

KEY_FILE="${DEPLOY_SSH_DIR}/id_ed25519_ci_${ENV_NAME}"
if [ -f "${KEY_FILE}" ]; then
    echo "  ✓ Key already exists — keeping it."
else
    ssh-keygen -t ed25519 -f "${KEY_FILE}" -N "" -C "ci-deploy@${REPO_NAME}-${ENV_NAME}"
    echo "  ✓ Key generated: ${KEY_FILE}"
fi

touch "${DEPLOY_SSH_DIR}/authorized_keys"
cat "${KEY_FILE}.pub" >> "${DEPLOY_SSH_DIR}/authorized_keys"
sort -u -o "${DEPLOY_SSH_DIR}/authorized_keys" "${DEPLOY_SSH_DIR}/authorized_keys"
chmod 600 "${DEPLOY_SSH_DIR}/authorized_keys"
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${DEPLOY_SSH_DIR}"
echo "  ✓ Public key installed in authorized_keys."

PRIVATE_KEY="$(cat "${KEY_FILE}")"

# ── Deployment directory ─────────────────────────────────
echo ""
echo "=== Creating deployment directory ==="
mkdir -p "${TARGET_DIR}"
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${DEPLOY_ROOT}"
echo "  ✓ ${TARGET_DIR}"

# ── Clone / update repository ────────────────────────────
echo ""
echo "=== Setting up repository (${BRANCH} branch) ==="
if [ -d "${TARGET_DIR}/.git" ]; then
    echo "  ✓ Already cloned — updating."
    sudo -u "${DEPLOY_USER}" git -C "${TARGET_DIR}" fetch origin
elif [ -n "$(ls -A "${TARGET_DIR}")" ]; then
    # Directory not empty (e.g. .env placed here already) — init in place.
    sudo -u "${DEPLOY_USER}" git -C "${TARGET_DIR}" init
    sudo -u "${DEPLOY_USER}" git -C "${TARGET_DIR}" remote add origin "${REPO_URL}"
    sudo -u "${DEPLOY_USER}" git -C "${TARGET_DIR}" fetch origin
    echo "  ✓ Initialized repo in existing directory."
else
    sudo -u "${DEPLOY_USER}" git clone "${REPO_URL}" "${TARGET_DIR}"
    echo "  ✓ Cloned."
fi
# HTTPS remote: no auth needed for public repo pulls.
sudo -u "${DEPLOY_USER}" git -C "${TARGET_DIR}" remote set-url origin "${REPO_URL}"
sudo -u "${DEPLOY_USER}" git -C "${TARGET_DIR}" checkout "${BRANCH}"
sudo -u "${DEPLOY_USER}" git -C "${TARGET_DIR}" pull --ff-only origin "${BRANCH}"
echo "  ✓ On branch ${BRANCH} (latest)."

# ── Detect public IP (best effort, for DEPLOY_HOST) ──────
PUBLIC_IP="$(curl -fsS --max-time 3 https://ifconfig.me 2>/dev/null || echo "<this server's IP>")"

# ── Done — remaining manual steps ────────────────────────
echo ""
echo "================================================================"
echo " SETUP COMPLETE: ${ENV_NAME}"
echo "================================================================"
echo ""
echo " Finish in GitHub — ${GH_ENVS_URL}"
echo ""
echo " 1. Create a GitHub environment named '${ENV_NAME}' (if missing)."
echo " 2. Add these secrets TO THE '${ENV_NAME}' ENVIRONMENT:"
echo "      DEPLOY_HOST    = ${PUBLIC_IP}"
echo "      DEPLOY_USER    = ${DEPLOY_USER}"
echo "      DEPLOY_SSH_KEY = <private key printed below>"
echo " 3. Place the .env file at:"
echo "      ${TARGET_DIR}/.env"
echo " 4. Push to '${BRANCH}' — the deploy workflow will fire."
if [ "${ENV_NAME}" = "prod" ]; then
echo " 5. Optional but recommended: on the 'prod' environment, enable"
echo "    'Required reviewers' so production deploys need a manual OK."
else
echo " 5. To provision production too, run this script again with 'prod'"
echo "    (on this server or a different one)."
fi
echo ""
echo " Optional hygiene: the private key also lives at ${KEY_FILE} —"
echo " delete it once the GitHub secret is saved (re-running this"
echo " script generates a fresh key if you ever lose the secret)."
echo ""
echo "----------------------------------------------------------------"
echo " PRIVATE KEY for GitHub secret DEPLOY_SSH_KEY (${ENV_NAME}):"
echo "----------------------------------------------------------------"
echo "${PRIVATE_KEY}"
echo "----------------------------------------------------------------"
