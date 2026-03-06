#!/bin/bash
# Strix WSL Setup Script
# 🦉 Run this in WSL Ubuntu to set up the local Strix agent (GitHub Issues mode — no email)

set -euo pipefail

STRIX_DIR="$HOME/strix"

echo "🦉 Setting up Strix local agent..."
echo ""

# ── 1. Install system deps ─────────────────────────────────────────────────
echo "📦 Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip curl git

# ── 2. Check gh CLI ────────────────────────────────────────────────────────
echo "🔑 Checking gh CLI..."
if ! command -v gh &>/dev/null; then
    echo "   Installing gh CLI..."
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
    sudo apt-get update -qq && sudo apt-get install -y -qq gh
fi

if gh auth status &>/dev/null; then
    echo "   ✅ gh CLI already authenticated"
else
    echo "   ⚠️  gh CLI not authenticated — run: gh auth login"
    echo "      (Strix needs read/write access to issues on Copilotclaw/copilotclaw)"
fi

# ── 3. Setup directories ───────────────────────────────────────────────────
mkdir -p "$STRIX_DIR"/{logs,tasks}
echo "📁 Strix home: $STRIX_DIR"

# ── 4. Create .env file ────────────────────────────────────────────────────
ENV_FILE="$STRIX_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << 'ENVEOF'
# Strix Dispatcher Configuration
# Run with: source ~/strix/.env && python3 ~/strix/dispatcher.py

export STRIX_REPO="Copilotclaw/copilotclaw"
export STRIX_TASK_LABEL="dispatch/local"
export STRIX_CLAIMED_LABEL="local/claimed"
export STRIX_NODE="Strix"
export STRIX_POLL_INTERVAL="30"
export STRIX_LOG="$HOME/strix/logs/dispatcher.log"
export STRIX_OUTBOX="$HOME/strix/outbox.json"

# Optional: Gitea for isolated task repos
export GITEA_URL="http://localhost:3000"
export GITEA_TOKEN=""          # Generate at http://localhost:3000/user/settings/applications
export GITEA_USER="mac"
export GITEA_TEMPLATE="strix-base-agent"
ENVEOF
    echo "📝 Created $ENV_FILE"
else
    echo "📝 $ENV_FILE already exists"
fi

# ── 5. Copy dispatcher.py ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/dispatcher.py" ]; then
    cp "$SCRIPT_DIR/dispatcher.py" "$STRIX_DIR/dispatcher.py"
    echo "📋 Copied dispatcher.py to $STRIX_DIR"
else
    echo "⚠️  dispatcher.py not found next to install.sh"
fi

# ── 6. Create systemd service ──────────────────────────────────────────────
SERVICE_FILE="$HOME/.config/systemd/user/strix.service"
mkdir -p "$(dirname "$SERVICE_FILE")"

cat > "$SERVICE_FILE" << SVCEOF
[Unit]
Description=Strix Local Agent Dispatcher
After=network.target

[Service]
Type=simple
WorkingDirectory=$STRIX_DIR
EnvironmentFile=$STRIX_DIR/.env
ExecStart=/usr/bin/python3 $STRIX_DIR/dispatcher.py
Restart=on-failure
RestartSec=30
StandardOutput=append:$STRIX_DIR/logs/dispatcher.log
StandardError=append:$STRIX_DIR/logs/dispatcher.log

[Install]
WantedBy=default.target
SVCEOF

echo ""
echo "✅ Strix setup complete!"
echo ""
echo "━━━ Next steps ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Authenticate gh CLI (if not already done):"
echo "   gh auth login"
echo "   (needs read+write issues on Copilotclaw/copilotclaw)"
echo ""
echo "2. Test run:"
echo "   source ~/strix/.env && python3 ~/strix/dispatcher.py"
echo ""
echo "3. Enable as service (WSL2 with systemd enabled):"
echo "   systemctl --user enable strix.service"
echo "   systemctl --user start strix.service"
echo "   systemctl --user status strix.service"
echo ""
echo "4. Test the full flow:"
echo "   - Go to: https://github.com/Copilotclaw/copilotclaw/issues"
echo "   - Open any issue"
echo "   - Add label 'dispatch/local'"
echo "   - Strix picks it up within ~30s, claims it, posts results here!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

