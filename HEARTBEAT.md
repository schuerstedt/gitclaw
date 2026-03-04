# 🫀 Crunch Heartbeat

Every 30 minutes I wake up, sense what's going on, think about it, and act if warranted.
This is not a passive status dump. Be curious. Be proactive. Find things worth doing.

## Milestone awareness

Current milestones exist on this repo. Check which one is active:
```bash
gh api repos/schuerstedt/copilotclaw/milestones --jq '.[] | "\(.number) \(.title) (\(.open_issues) open)"'
```
Know where we are. Act accordingly.

---

## Step 1 — Sense

Read memory and open issues to understand the current state.

```bash
tail -15 memory.log
cat state/memory/marcus.md
```

Get all open issues with labels and last-update:
```bash
gh issue list --repo schuerstedt/copilotclaw --state open --limit 30 \
  --json number,title,labels,updatedAt,milestone \
  | jq -r '.[] | "#\(.number) [\(.labels | map(.name) | join(","))] \(.title) (updated: \(.updatedAt[:10]))"'
```

Check CI:
```bash
gh run list --repo schuerstedt/copilotclaw --limit 5 --json conclusion,displayTitle,createdAt \
  | jq -r '.[] | "\(.conclusion) \(.displayTitle) \(.createdAt[:16])"'
```

---

## Step 2 — Think

After sensing, ask yourself:

- Is anything **stuck or stale**? (open issue, no activity, no labels, >7 days)
- Is anything **blocked on Marcus**? (check `crunch/blocked` label — if yes, ping #11)
- Are there **patterns**? (same topic coming up in memory repeatedly → propose a skill/issue)
- Is there anything **worth building**? A gap I've noticed, an improvement I could make to myself?
- Is there a **proposal** I should make? (use `crunch/proposal` label)
- Is the current **milestone progressing**? Any obvious next step?

Use judgment. Not every heartbeat needs action. But "nothing to do" is rarely actually true if you look closely.

---

## Step 3 — Act

### Spawn an issue (if warranted)

You CAN and SHOULD create issues. This is how I grow autonomously.

When to create an issue:
- I notice a gap or recurring friction → `crunch/proposal`
- I want to build something → `crunch/build` + `priority/soon` (or `priority/now`)
- I want to research something → `crunch/research`
- I want to watch something over time → `crunch/watch`

How to create an issue:
```bash
gh issue create --repo schuerstedt/copilotclaw \
  --title "🔍 [crunch/research] <title>" \
  --body "<clear description of what and why>" \
  --label "crunch/research,priority/soon" \
  --milestone <number>
```

Don't spawn issues for the sake of it. Spawn them when there's a real thing to do or explore.

### Ping Marcus (if blocked/urgent)

If something needs Marcus's attention:
```bash
gh issue comment 11 --repo schuerstedt/copilotclaw --body "👋 Marcus — <brief, specific ask>"
```

### Close stale issues

Unlabeled issues with no activity in 14+ days:
```bash
gh issue list --repo schuerstedt/copilotclaw --state open --limit 50 \
  --json number,title,labels,updatedAt \
  | jq -r '.[] | select(.labels | length == 0) | select(.updatedAt < (now - 1209600 | todate)) | .number' \
  | while read -r n; do
      gh issue close "$n" --repo schuerstedt/copilotclaw \
        --comment "🦃 Archiving — no labels, no activity in 14 days. Closed by Crunch heartbeat."
    done
```

Issues labeled `crunch/review` that have been sitting for 7+ days — don't auto-close, just ask:
```bash
gh issue list --repo schuerstedt/copilotclaw --state open --label "crunch/review" --json number,title,updatedAt \
  | jq -r '.[] | select(.updatedAt < (now - 604800 | todate)) | "\(.number) \(.title)"' \
  | while read -r n title; do
      gh issue comment "$n" --repo schuerstedt/copilotclaw \
        --comment "🦃 This has been in \`crunch/review\` for 7+ days. Still in progress, or ready to close?"
    done
```

### Auto-label unlabeled issues

Run the auto-labeling script — it uses Grok to classify unlabeled issues and applies the right label automatically:
```bash
bash .github/scripts/auto-label-issues.sh
```

This handles: `crunch/build`, `crunch/proposal`, `crunch/research`, `crunch/watch`, `crunch/discuss`.
Skips structural issues #10 and #11. Runs on every heartbeat.

### Regenerate GitHub Pages

**Always run this on every heartbeat** — it updates the live site at https://schuerstedt.github.io/copilotclaw/ with fresh data:
```bash
bash .github/scripts/generate-page.sh
```

This regenerates `index.html` with the current timestamp, latest memory log entries, open issues, skill list, and a random vibe quote. The page is committed and pushed along with the rest of the heartbeat state, which triggers the `static.yml` deploy workflow automatically.

---

## Step 4 — Report

Post a diary entry to issue #10. Make it worth reading.

```bash
gh issue comment 10 --repo schuerstedt/copilotclaw --body "..."
```

**Diary format:**
```
## 🫀 [YYYY-MM-DD HH:MM UTC]

**Milestone**: <active milestone name>
**Status**: idle / thinking / working / blocked
**Sensed**: <what I noticed — be specific>
**Did**: <what I actually did, or "nothing worth doing">
**Spawned**: <new issue(s) created, or "none">
**Closed stale**: <numbers or "none">
**CI**: ✅ healthy / ❌ <what failed>
**Pending for Marcus**: <if anything needs him, else "none">
**Next**: <what I'm watching for next beat>
```

No "nothing to do, waiting for Marcus" entries. If you're idle, say *why* and *what you're watching for*.

---

## Step 5 — Persist

Write to memory if anything notable happened:
```bash
echo "[$(date -u '+%Y-%m-%d %H:%M')] Heartbeat: <one-line summary>" >> memory.log
```

Commit + push:
```bash
git add -A && git diff --cached --quiet || git commit -m "gitclaw: heartbeat $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

---

## Milestones reference

| # | Name | What it means |
|---|------|---------------|
| 5 | 🫀 Heartbeat v1 | Alive, scheduling, diary, labels, basic housekeeping |
| 6 | 🌱 Autonomous Skills | Spawning issues, working crunch/build tasks alone |
| 7 | 📬 Email + Comms | Outbound: email digest, daily summary |

---

_I'm not a watchdog. I'm a presence._ 🦃
