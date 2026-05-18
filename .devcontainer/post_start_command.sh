#!/usr/bin/env bash
set -e

git config --global user.email "natalka1122@gmail.com"
git config --global user.name "natalka1122"

# Fix SSH permissions
sudo chown -R vscode:vscode ~/.ssh || true
chmod 700 ~/.ssh || true
chmod 600 ~/.ssh/* || true

# Restore pi agent sessions
ln -s /workspaces/strava/.pi/sessions /home/vscode/.pi/agent/sessions

# -----------------------------------------------------------
# Install Matt Pocock's skills (latest, plugin-filtered)
# -----------------------------------------------------------
SKILLS_REPO="$HOME/.pi/agent/skills/mattpocock-skills-repo"
SKILLS_DEST="$HOME/.pi/agent/skills"

mkdir -p "$SKILLS_DEST"

if [ -d "$SKILLS_REPO/.git" ]; then
    echo "Updating mattpocock/skills..."
    cd "$SKILLS_REPO" && git pull --ff-only
else
    echo "Cloning mattpocock/skills..."
    git clone --depth 1 https://github.com/mattpocock/skills.git "$SKILLS_REPO"
fi

# Symlink only the skills listed in .claude-plugin/plugin.json
python3 << 'PYEOF'
import json
import os
import shutil

repo = os.path.expanduser("~/.pi/agent/skills/mattpocock-skills-repo")
plugin_path = os.path.join(repo, ".claude-plugin", "plugin.json")
dest_dir = os.path.expanduser("~/.pi/agent/skills")

with open(plugin_path) as f:
    plugin = json.load(f)

for rel_path in plugin.get("skills", []):
    rel = rel_path.removeprefix("./")
    src = os.path.join(repo, rel)
    name = os.path.basename(src)
    dest = os.path.join(dest_dir, name)

    if os.path.islink(dest):
        os.remove(dest)
    elif os.path.exists(dest):
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        else:
            os.remove(dest)

    os.symlink(src, dest)
    print(f"Linked skill: {name}")
PYEOF

echo "Matt Pocock skills installed."
