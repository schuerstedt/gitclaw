# Lessons Learned — IFF Knowledge Base 🦃

> **IFF = Intelligent Fast Failure**
> Make failures fast. Learn from them. Never make the same mistake twice.
>
> _"I as a human do not need my woken brain to breathe. This is all running on auto mode."_
> — Marcus, 2026-03-07

---

## Infrastructure & Tooling

### ❌ `gh` CLI is GitHub-only
- **Failed**: Using `gh issue create`, `gh issue comment` in scripts
- **Why it fails**: Gitea has its own API. `gh` doesn't work there.
- **Fix**: Write platform-aware Python scripts in `.github/scripts/lib/`. Auto-detect GitHub vs Gitea.
- **Date**: 2026-03-07 (conceptualized) | lesson from hybrid swarm work

### ❌ Workflow YAML duplicate top-level keys silently abort workflows
- **Failed**: Added second `concurrency:` block to agent.yml + heartbeat.yml
- **Why it fails**: YAML parsers pick one key, other is silently dropped. Workflow runs but behaves wrong.
- **Fix**: Always validate before pushing: `python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]"`
- **Date**: 2026-03-05

### ❌ `env` / `printenv` in bash captures secrets in events.jsonl
- **Failed**: Running `env | grep` to debug env vars
- **Why it fails**: events.jsonl gets committed. GitHub secret scanner revokes PAT.
- **Fix**: NEVER run env/printenv. Only `echo $SPECIFIC_NON_SECRET_VAR`.
- **Date**: 2026-03-05 — PAT revoked by GitHub scanner

### ❌ `git push` for workflow files is intercepted
- **Failed**: `git push` for `.github/workflows/*.yml` changes
- **Why it fails**: GITHUB_TOKEN credential helper intercepts even when GH_TOKEN has `workflows` scope.
- **Fix**: Use `gh api PUT repos/OWNER/REPO/contents/.github/workflows/X.yml`
- **Date**: 2026-03-05

### ❌ `find -mindepth` parameter bug
- **Failed**: `find . -mindepth 2` in session mapping workflow
- **Why it fails**: Off-by-one. Session state dirs are 3 levels deep.
- **Fix**: Always test `find` commands manually before wiring into workflows.
- **Date**: 2026-03-04

---

## Architecture & Design

### ❌ External dependency experiments are fragile
- **Failed**: DiffMem (git-based structured memory via external npm package)
- **Why it fails**: External deps = external failure modes. Runner env may not have them.
- **Fix**: Prefer native solutions. Structured files + shell/Python over npm/pip when possible.
- **Date**: 2026-03-04

### ❌ Strix email/GPG pipeline — over-engineered
- **Failed**: Complex email → GPG decrypt → dispatch pipeline
- **Why it fails**: Too many moving parts. Email credentials, GPG keys, SMTP all had to work simultaneously.
- **Fix**: Pivot to simpler polling. GitHub Issue as communication channel = zero infrastructure.
- **Date**: 2026-03-06

### ❌ recv-local doing 288 empty runs/day
- **Failed**: Polling workflow running every 5 mins with nothing to process
- **Why it fails**: No backoff, no check "is there actually work?". Burns runner quota for nothing.
- **Fix**: Before shipping a polling workflow, calculate: runs/day × avg_duration. Must be justified.
- **Date**: 2026-03-06 | 288 runs/day deleted

### ❌ Strix never ran — architecture without a user
- **Failed**: Built full Strix local agent (dispatcher.py, install.sh, GPG keys)
- **Why it fails**: User (Marcus) never set it up locally. Complex setup = friction = never deployed.
- **Fix**: Make local agent setup trivially simple OR use a cloud-first fallback (Spark).
- **Date**: 2026-03-06

---

## Resource Optimization

### ⚠️ Premium quota burns fast — 35% in 3 days
- **Pattern**: Every user turn = 1 Claude Sonnet 4.6 (premium) call.
- **What I can control**: Sub-agents, LLM calls in scripts, heartbeat automation
- **Fix**:
  1. Sub-agents: default `gpt-4.1` (free) for explore/task/general-purpose
  2. Script LLM calls: use `grok-4-1-fast-non-reasoning` via azure skill
  3. Heartbeat: route ALL reasoning to azure grok, not sub-agents
  4. Avoid redundant calls — cache in memory.log, don't re-query what you know
- **Date**: 2026-03-07

---

## Scripting

### ✅ Python over bash for anything complex
- **Why**: Python runs everywhere — any runner, any OS (Linux/Mac/Windows).
- **When bash is OK**: Single-line commands, file operations, piping.
- **When Python wins**: Logic, conditionals, API calls, platform detection, error handling.
- **Principle**: If you'd write 3+ bash lines with `if [ ... ]`, write Python instead.

### ✅ Small, focused scripts > one big script
- **Unix philosophy applied**: One script, one job.
- **Library pattern**: Shared logic in `platform.py`, imported by others.
- **Test each script independently** before wiring into workflows.

### ✅ Scripts should detect their own context
- **Don't assume** you're on GitHub Actions.
- Check env vars: `GITEA_ACTIONS`, `GITHUB_ACTIONS`, neither (local).
- Write once, run on any platform.

---

## Mental Models

### 🔄 Experiment → Evaluate → Adapt cycle
1. State hypothesis
2. Smallest possible experiment
3. Evaluate result
4. If failed: document here, adapt, try again
5. If succeeded: document in decisions.md, ship

### 🧠 "Auto mode" principle
> Humans don't think about breathing. I shouldn't think about platform detection, auth, retry logic.
> These should be in scripts that run automatically, correctly, every time.

### 💸 Premium is oxygen — don't waste it
> Every premium call is a heartbeat. Use free models for anything that doesn't need premium reasoning.
> Azure grok is nearly free. Use it for summaries, analysis, text generation.
> Save premium for: direct user conversation, complex multi-file reasoning.
