#!/bin/bash
# Export Strix's keys from GitHub Secrets to files for WSL import.
# Run this in WSL: bash export-keys.sh
# Requires: gh CLI authenticated as schuerstedt or Copilotclaw

set -euo pipefail

STRIX_DIR="$HOME/strix/keys"
mkdir -p "$STRIX_DIR"

echo "🔑 Fetching keys from GitHub Secrets..."
echo "   (You need gh CLI authenticated + Copilotclaw repo access)"

# The secrets hold the armored key text — fetch via repo secret API
# Note: Secret VALUES can't be read back via API (GitHub design).
# Marcus must paste these manually from the session output.

cat << 'MSG'

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 KEY IMPORT INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Crunch generated 2 GPG keypairs during setup:
  Crunch Cloud: 3AAFF44FE0F12E564E84278797BFAD6DC2176CA7
  Strix Local:  ACD07B709FE5CD2AFD583CE7B306DEC4488EC11D

The keys are stored as GitHub Secrets in Copilotclaw/copilotclaw.
GitHub doesn't let you read secrets back via API (security by design).

TO GET THE KEY FILES:
Ask Crunch (create a GitHub issue) to output:
  "Please print the Strix private key and Crunch public key"

OR: In the Copilot CLI session, run:
  cat /tmp/crunch_public.asc
  cat /tmp/strix_private.asc

Then save them to:
  ~/strix/keys/crunch_public.asc
  ~/strix/keys/strix_private.asc

Then import:
  gpg --import ~/strix/keys/crunch_public.asc
  gpg --import ~/strix/keys/strix_private.asc
  echo "5\ny\n" | gpg --command-fd 0 --expert \
    --edit-key 3AAFF44FE0F12E564E84278797BFAD6DC2176CA7 trust

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MSG
