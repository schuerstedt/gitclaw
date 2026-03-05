#!/usr/bin/env bash
# autonomous-pickup.sh
# Scans for crunch/build issues labeled priority/now and posts a pickup comment
# using BILLING_PAT (authenticates as schuerstedt, not github-actions[bot]),
# which triggers agent.yml to work the issue.

set -euo pipefail

REPO="Copilotclaw/copilotclaw"
TOKEN="${BILLING_PAT:-}"

if [[ -z "$TOKEN" ]]; then
  echo "autonomous-pickup: BILLING_PAT not set, skipping"
  exit 0
fi

# Find crunch/build + priority/now issues, not updated in the last 2 hours (to avoid thrashing)
THRESHOLD=$(date -u -d '2 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || \
            date -u -v-2H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")

if [[ -z "$THRESHOLD" ]]; then
  echo "autonomous-pickup: could not compute threshold date, skipping"
  exit 0
fi

# Check quota before doing anything
SCRIPT_DIR="$(dirname "$0")"
if ! bash "$SCRIPT_DIR/quota-guard.sh" check 2>/dev/null; then
  echo "autonomous-pickup: quota guard blocked — skipping pickup"
  exit 0
fi

CANDIDATES=$(GH_TOKEN="$TOKEN" gh issue list --repo "$REPO" \
  --state open \
  --label "crunch/build,priority/now" \
  --limit 5 \
  --json number,title,updatedAt \
  | jq -r --arg threshold "$THRESHOLD" \
    '.[] | select(.updatedAt < $threshold) | "\(.number) \(.title)"')

if [[ -z "$CANDIDATES" ]]; then
  echo "autonomous-pickup: no priority/now crunch/build issues ready for pickup"
  exit 0
fi

# Pick the first candidate
FIRST=$(echo "$CANDIDATES" | head -1)
NUM=$(echo "$FIRST" | cut -d' ' -f1)
TITLE=$(echo "$FIRST" | cut -d' ' -f2-)

echo "autonomous-pickup: posting pickup comment on #$NUM — $TITLE"

BODY="🤖 Heartbeat auto-pickup: working this issue now.

**Issue**: #${NUM} — ${TITLE}

Read the issue body and implement what's described. When done, label the issue \`crunch/review\` and summarize what you did."

GH_TOKEN="$TOKEN" gh issue comment "$NUM" --repo "$REPO" --body "$BODY"

echo "autonomous-pickup: comment posted on #$NUM — agent.yml should trigger shortly"
