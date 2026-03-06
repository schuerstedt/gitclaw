#!/bin/bash
# Strix WSL Setup Script
# 🦉 Run this in WSL Ubuntu to set up the local Strix agent

set -euo pipefail

STRIX_DIR="$HOME/strix"
CRUNCH_GPG_FINGERPRINT="3AAFF44FE0F12E564E84278797BFAD6DC2176CA7"
STRIX_GPG_FINGERPRINT="ACD07B709FE5CD2AFD583CE7B306DEC4488EC11D"

echo "🦉 Setting up Strix local agent..."
echo ""

# ── 1. Install system deps ─────────────────────────────────────────────────
echo "📦 Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq gnupg python3 python3-pip curl git

# ── 2. Install Python packages ─────────────────────────────────────────────
echo "🐍 Installing Python packages..."
pip3 install --quiet python-gnupg

# ── 3. Setup directories ───────────────────────────────────────────────────
mkdir -p "$STRIX_DIR"/{logs,keys,tasks}
echo "📁 Strix home: $STRIX_DIR"

# ── 4. Import GPG keys ─────────────────────────────────────────────────────
echo ""
echo "🔑 Setting up GPG keys..."
echo "   You need two key files:"
echo "   1. crunch_public.asc  — Crunch's public key (to verify cloud dispatches)"
echo "   2. strix_private.asc  — Strix's private key (to sign results)"
echo ""
echo "   Download from the copilotclaw repo secrets OR copy from this session."
echo "   Place them in: $STRIX_DIR/keys/"
echo ""

if [ -f "$STRIX_DIR/keys/crunch_public.asc" ]; then
    gpg --import "$STRIX_DIR/keys/crunch_public.asc" 2>&1 | grep -E "imported|already"
    # Trust Crunch's key
    echo -e "5\ny\n" | gpg --command-fd 0 --expert --edit-key "$CRUNCH_GPG_FINGERPRINT" trust 2>/dev/null || true
    echo "   ✅ Crunch public key imported"
else
    echo "   ⚠️  $STRIX_DIR/keys/crunch_public.asc not found — import manually later:"
    echo "      gpg --import crunch_public.asc"
fi

if [ -f "$STRIX_DIR/keys/strix_private.asc" ]; then
    gpg --import "$STRIX_DIR/keys/strix_private.asc" 2>&1 | grep -E "imported|already"
    echo "   ✅ Strix private key imported"
else
    echo "   ⚠️  $STRIX_DIR/keys/strix_private.asc not found — import manually later:"
    echo "      gpg --import strix_private.asc"
fi

# ── 5. Create .env file ────────────────────────────────────────────────────
ENV_FILE="$STRIX_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << 'ENVEOF'
# Strix Dispatcher Configuration
# Fill in the blanks and run: source ~/strix/.env && python3 ~/strix/dispatcher.py

export STRIX_IMAP_HOST="mx2f20.netcup.net"
export STRIX_IMAP_PORT="993"
export STRIX_SMTP_HOST="mx2f20.netcup.net"
export STRIX_SMTP_PORT="465"
export STRIX_LOCAL_EMAIL="crunchlocal.agent@aigege.de"
export STRIX_LOCAL_PASSWORD="D8_298kqn"
export STRIX_CLOUD_EMAIL="crunchcloud.agent@aigege.de"
export CRUNCH_GPG_FINGERPRINT="3AAFF44FE0F12E564E84278797BFAD6DC2176CA7"
export STRIX_GPG_FINGERPRINT="ACD07B709FE5CD2AFD583CE7B306DEC4488EC11D"
export GITEA_URL="http://localhost:3000"
export GITEA_TOKEN=""          # Generate at http://localhost:3000/user/settings/applications
export GITEA_USER="mac"
export GITEA_TEMPLATE="strix-base-agent"
export STRIX_POLL_INTERVAL="30"
export STRIX_LOG="$HOME/strix/logs/dispatcher.log"
ENVEOF
    echo "📝 Created $ENV_FILE — review and fill in GITEA_TOKEN"
else
    echo "📝 $ENV_FILE already exists"
fi

# ── 6. Copy dispatcher.py ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/dispatcher.py" ]; then
    cp "$SCRIPT_DIR/dispatcher.py" "$STRIX_DIR/dispatcher.py"
    echo "📋 Copied dispatcher.py to $STRIX_DIR"
else
    echo "⚠️  dispatcher.py not found next to install.sh"
fi

# ── 7. Create systemd service ──────────────────────────────────────────────
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
echo "━━━ Next steps ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Import GPG keys (if not done above):"
echo "   Copy crunch_public.asc + strix_private.asc to ~/strix/keys/"
echo "   Then run this script again."
echo ""
echo "2. Generate Gitea API token:"
echo "   Open http://localhost:3000/user/settings/applications"
echo "   Create token, then add to ~/strix/.env:"
echo "   export GITEA_TOKEN=\"your-token-here\""
echo ""
echo "3. Test run:"
echo "   source ~/strix/.env && python3 ~/strix/dispatcher.py"
echo ""
echo "4. Enable as service (WSL2 with systemd enabled):"
echo "   systemctl --user enable strix.service"
echo "   systemctl --user start strix.service"
echo "   systemctl --user status strix.service"
echo ""
echo "5. Test the full flow:"
echo "   - Go to GitHub: https://github.com/Copilotclaw/copilotclaw/issues"
echo "   - Open any issue"
echo "   - Add label 'dispatch/local'"
echo "   - Strix should receive the task within 30s!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
