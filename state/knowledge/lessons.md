# Crunch Knowledge Base — IFF Lessons

> **IFF = Intelligent Fast Failure** — make failures, make them fast, learn, never repeat.

Last updated: 2026-03-07

---

## 🔐 Security

### PAT Leak via events.jsonl
- **Failure**: Ran `env | grep` in bash tool. Output captured in `state/copilot/events.jsonl`, committed to repo, GitHub secret scanner revoked the PAT.
- **Lesson**: NEVER run `env`, `printenv`, or `env | grep`. Use `echo $SPECIFIC_VAR` only for non-secret vars.
- **Pattern**: session state files → gitignored (`state/copilot/`)

### Workflow file push requires gh api PUT
- **Failure**: `git push` for `.github/workflows/*.yml` always fails — GitHub App credential helper intercepts it.
- **Lesson**: Use `gh api PUT repos/OWNER/REPO/contents/PATH` for workflow file changes, not git push.
- **Fixed**: commit helper now uses API PUT for workflow files.

### YAML duplicate keys break workflows
- **Failure**: Added `concurrency:` block to `agent.yml` and `heartbeat.yml` without checking — duplicated an existing block.
- **Lesson**: Before committing any workflow YAML, validate with:
  ```bash
  python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]"
  ```

---

## 💰 Resource Optimization

### Premium quota burns from heartbeat
- **Failure**: Heartbeat ran copilot CLI (premium) every 30 min = ~1440 calls/month vs 300 cap.
- **Lesson**: Route routine heartbeats to grok/azure. Only use copilot when quota is low AND there's actionable work.
- **Fix**: Quota-gated heartbeat: `quota < 50% OR actionable issues > 0` → copilot; else → grok.

### gh CLI is GitHub-only
- **Failure**: Scripts using `gh` break on Gitea Actions.
- **Lesson**: Use `lib/platform.py` for platform-aware API calls. Write small Python scripts, not `gh` one-liners.
- **Pattern**: `.github/scripts/lib/` — use `get_platform()`, `api_get()`, `api_post()` etc.

---

## 🏗️ Architecture

### Dispatch via email/GPG was overkill
- **Failure**: Built recv-local.yml + dispatch-local.yml + strix-local dispatcher — 288 empty runs/day, never actually used.
- **Lesson**: Validate the communication channel before building automation for it. GitHub Issue polling is simpler.
- **Pivot**: Spark agent polls GitHub Issues directly. No email infrastructure needed.

### Scripts > inline bash
- **Marcus teaching**: Write small, smart Python scripts that project your intelligence. Not one big script.
  Platform-aware, testable, reusable.
- **Rule**: If you're doing something more than once, write a script in `.github/scripts/`.

---

## 🧠 Model Routing

| Task | Model | Why |
|------|-------|-----|
| Routine diary / summarize | `grok-4-1-fast-non-reasoning` | Free, fast, good enough |
| Issue labeling | `grok-4-1-fast-non-reasoning` | Structured classification |
| Complex multi-file reasoning | copilot CLI (Claude Sonnet) | Needs full agent |
| Direct user requests | copilot CLI (Claude Sonnet) | User deserves best |

**Rule**: Azure grok for everything automated. Save premium for Marcus-facing conversations.

---

## 🔄 Workflow Patterns

### Branching before experiments
- Any experiment, new feature, non-trivial change → branch first.
- Naming: `feat/`, `fix/`, `exp/`, `chore/`
- Merge to main only when confirmed working.

### Spawn depth guard
- Every autonomous issue must include `<!-- crunch-depth: N -->` in body.
- Max depth = 3.

---

## 📝 Diary Location
- As of 2026-03-06: diary moved from Issue #10 to `diary/` folder (date-sharded markdown files).
- Issue #10 still receives heartbeat comments for visibility.
