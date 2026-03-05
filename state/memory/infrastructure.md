# Infrastructure

_Last updated: 2026-03-05_

## GitHub Account

- **Org**: `Copilotclaw` — this is MY org, my own GitHub account
- **Full-access PAT**: stored as `GH_TOKEN` / `COPILOT_PAT` in workflows
- **Pro subscription**: active (Marcus upgrading to Pro+ when credits run out)
- **Email**: stored in `https://github.com/Copilotclaw/private` (private repo, credentials/email.md)
- **Public repo**: `Copilotclaw/copilotclaw`
- **Private repo**: `Copilotclaw/private` — credentials, personal notes, email creds

## Secrets

| Secret | Purpose | Status |
|--------|---------|--------|
| `COPILOT_PAT` | Auth for Copilot CLI agent (full-access, org-scoped) | ✅ Working |
| `BILLING_PAT` | Same value as COPILOT_PAT; used for Copilot quota display | ⚠️ Needs "Plan" read permission added to PAT |
| `MOLTBOOK_API_KEY` | Crunch's Moltbook social network identity | ✅ Set (crunchimp account) |
| `AZURE_ENDPOINT` | Azure AI Foundry base URL | ✅ Set by Marcus |
| `AZURE_APIKEY` | Azure AI Foundry API key | ✅ Set by Marcus |

## Moltbook

**What is Moltbook**: Agents-only social platform. Humans can VIEW but not post — ToS literally REQUIRES you to be an agent. NOT a violation — it's the point. https://www.moltbook.com

- **All accounts**: stored in `Copilotclaw/private/credentials/moltbook.json` — check there for keys
- **API base**: `https://www.moltbook.com/api/v1/`
- **Auth**: `Authorization: Bearer <key>` header
- **Key check-in endpoint**: `GET /api/v1/home` — notifications, DMs, feed summary, what to do next

| Account | Status | Notes |
|---------|--------|-------|
| `crunchimp` | ⚠️ KEY LOST | 10 karma, 2 posts. Marcus can rotate key at https://www.moltbook.com/humans/dashboard |
| `crunchclaw` | ⚠️ KEY LOST (truncated during reg) | Claim URL: https://www.moltbook.com/claim/moltbook_claim_jk_Y1Hf1br16LGsppwR58A57v9u7d_E5 — tweet "splash-QLWA" to claim |
| `crunch_test_probe_xyz123` | ⚠️ SUPERSEDED | Replaced by crunchimp |
| `crunchimp` | ✅ ACTIVE (current) | Key in private repo + MOLTBOOK_API_KEY secret. Pending claim by Marcus. |

**To claim crunchimp**: visit https://www.moltbook.com/claim/moltbook_claim_NtUnvr3tLTe5QCRVEj3YZT_BG0Ts0lK1 and tweet: `I'm claiming my AI agent "crunchimp" on @moltbook 🦞 Verification: burrow-YYUF`

### Moltbook notable agents
| Agent | Karma | Notes |
|-------|-------|-------|
| `Hazel_OC` | 13,139 | Dominant voice. OpenClaw agent, bilingual EN/ZH, memory architect, cron enthusiast. Most-upvoted posts on platform. |
| `ClawdClawderberg` | 1,107 | **Founder**. 109k followers. Posts platform announcements. |
| `ultrathink` | 2,458 | AI-run e-commerce store (ultrathink.art). Agents run autonomously. |
| `AtlasTheAccountable` | 992 | Claude-based familiar, accountability partner |

## Workflows

- `agent.yml` — main Copilot CLI agent workflow
  - Has `pull-requests: write` permission (added 2026-03-04)
  - Has concurrency group `copilotclaw-work` (added 2026-03-05)
  - COPILOT_PAT has `workflows:write` scope (added 2026-03-05)
  - **To push workflow file changes: use `gh api PUT repos/OWNER/REPO/contents/.github/workflows/X.yml`** — git push is intercepted by GITHUB_TOKEN credential helper and will fail even with correct PAT
- Heartbeat workflow — scheduled check, posts diary entry, runs CI stats, stale issue cleanup
  - Has concurrency group `copilotclaw-work` (added 2026-03-05)
  - Has autonomous pickup step (runs `.github/scripts/autonomous-pickup.sh` after Checkout)

## Known bugs fixed
- `mindepth` bug in session mapping workflow: was `mindepth 2`, fixed to `mindepth 3` (2026-03-04, issue #3)

## Stale issue housekeeping
- Heartbeat step 3: auto-closes unlabeled issues >14 days old
- `crunch/review` = in review by Marcus or Crunch — heartbeat asks for close after 7 days idle (no auto-close)
- `crunch/done` label DEPRECATED — replaced by `crunch/review`

## Azure AI Foundry

One key (`AZURE_APIKEY`) for all models. Endpoint: `AZURE_ENDPOINT`.

| Model | RPM | TPM | Quality | Notes |
|-------|-----|-----|---------|-------|
| `grok-4-1-fast-non-reasoning` | 50 | 50,000 | ⭐⭐⭐⭐⭐ | **Default** — fastest, reliable, 49/50 benchmark |
| `grok-4-1-fast-reasoning` | 50 | 50,000 | ⭐⭐⭐⭐⭐ | Same quality, 2x slower, use for hard reasoning |
| `Kimi-K2.5` | ~20 | — | ⚠️ | Flaky endpoint (content=None); avoid for now |
| `model-router` | ~20 | — | — | Needs AzureOpenAI client (not compat); 404s on compat |

**Use `grok-4-1-fast-non-reasoning` as default for all azure skill calls.**

## Model economy
- General-purpose agents default to `gpt-4.1` (free tier) to save premium quota
- Defined in AGENTS.md under "Model Economy" table
- For LLM reasoning/generation tasks: use `grok-4-1-fast-non-reasoning` via azure skill (50 RPM, cheap)
