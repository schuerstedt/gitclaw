#!/usr/bin/env bash
# Auto-label unlabeled open issues using Grok classification.
# Called from heartbeat. Skips structural issues #10 #11.
#
# Requires: GITHUB_TOKEN, AZURE_ENDPOINT, AZURE_APIKEY
# Usage: bash .github/scripts/auto-label-issues.sh

set -euo pipefail

REPO="${GITHUB_REPOSITORY:-Copilotclaw/copilotclaw}"
SKIP_ISSUES="10 11"

echo "🏷️  Auto-labeling unlabeled issues..."

# Get unlabeled open issues
UNLABELED=$(gh issue list --repo "$REPO" --state open --limit 50 \
  --json number,title,body,labels \
  | jq -r '.[] | select(.labels | length == 0) | "\(.number)\t\(.title)\t\(.body[:300])"')

if [[ -z "$UNLABELED" ]]; then
  echo "No unlabeled issues found."
  exit 0
fi

LABELED_COUNT=0

while IFS=$'\t' read -r num title body; do
  # Skip structural issues
  if echo "$SKIP_ISSUES" | grep -qw "$num"; then
    continue
  fi

  echo "  → Issue #$num: $title"

  # Classify with Grok
  PROMPT="Classify this GitHub issue into exactly ONE label from this list:
crunch/build (implementing/creating/fixing/building something)
crunch/proposal (idea/suggestion/proposal for a new feature or change)
crunch/research (exploring/researching/reading/understanding something)
crunch/watch (monitoring/tracking something over time)
crunch/discuss (conversational, vague, unclear, or meta discussion)

Issue title: $title
Issue body: $body

Reply with ONLY the label name, nothing else."

  LABEL=$(python .github/skills/azure/scripts/llm.py \
    --model grok-4-1-fast-non-reasoning \
    --prompt "$PROMPT" \
    --max-tokens 20 2>/dev/null | tr -d '[:space:]' | head -c 40)

  # Validate label is one of the allowed set
  case "$LABEL" in
    crunch/build|crunch/proposal|crunch/research|crunch/watch|crunch/discuss)
      ;;
    *)
      echo "    ⚠️  Unexpected label '$LABEL' — falling back to crunch/discuss"
      LABEL="crunch/discuss"
      ;;
  esac

  # Apply label (create crunch/discuss if needed)
  if [[ "$LABEL" == "crunch/discuss" ]]; then
    # Ensure label exists
    gh label create "crunch/discuss" --repo "$REPO" --color "d93f0b" \
      --description "Conversational or meta discussion" 2>/dev/null || true
  fi

  gh issue edit "$num" --repo "$REPO" --add-label "$LABEL" 2>/dev/null && {
    echo "    ✅ Labeled #$num as $LABEL"
    LABELED_COUNT=$((LABELED_COUNT + 1))
  } || echo "    ❌ Failed to label #$num"

done <<< "$UNLABELED"

echo "🏷️  Done. Labeled $LABELED_COUNT issue(s)."
