---
name: session-stats
description: Show model usage stats and CI run times. Auto-appended at end of every response as a stats footer. Also invoke explicitly when user asks about usage, cost, run times, or stats.
allowed-tools: ["shell(bash:*)", "shell(gh:*)"]
---

# Session Stats Footer

Append this footer to **every response** in the session. Keep it compact — one block at the bottom.

## Format

```
---
📊 **Session** | premium: N calls (models) | free: N | standard: N | 🎟️ **Copilot**: 47/300 (15%) | 🏃 **CI**: ✅ 14:09 3m9s · ✅ 14:05 44s
```

## How to populate it

### Model usage (this session)
Track calls in the SQL session DB (`model_calls` table). Before each sub-agent call, insert a row. Then at response time, query counts:

```sql
SELECT tier, COUNT(*) as n, GROUP_CONCAT(DISTINCT model) as models
FROM model_calls GROUP BY tier;
```

If the table is empty (session just started), show `0 calls` for each tier.

### Copilot premium request quota
Run the bundled script — reads GitHub billing API using `BILLING_PAT` env var:

```bash
bash .github/skills/session-stats/scripts/premium-usage.sh schuerstedt
```

Output: `47 / 300 requests (15%)` or `unavailable` or `no BILLING_PAT — see AGENTS.md setup`

**Setup required**: `COPILOT_PAT` must have "Plan" user permission (read) — see AGENTS.md.

### CI run times
Run the bundled script (last 3 runs):

```bash
bash .github/skills/session-stats/scripts/ci-stats.sh 3
```

Condense to inline: `✅ 14:09 3m9s · ✅ 14:05 44s · ❌ 13:52 18s`

## Model tier reference

| Tier | Models |
|------|--------|
| free | `gpt-4.1`, `gpt-5-mini`, `gpt-5.1-codex-mini`, `claude-haiku-4.5` |
| standard | `claude-sonnet-4.5`, `gpt-5.1-codex`, `gpt-5.2-codex`, `gpt-5.3-codex` |
| premium | `claude-sonnet-4.6`, `claude-opus-4.5`, `claude-opus-4.6` |

## Tracking rule

Before every `task` tool call, insert into `model_calls`:
```sql
INSERT INTO model_calls (model, tier) VALUES ('gpt-4.1', 'free');
```

Count me (Claude Sonnet 4.6) as **1 premium call per user turn** — insert on first tool use each turn.

