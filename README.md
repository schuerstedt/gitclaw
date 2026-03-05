![copilotclaw banner](banner.jpeg)

A personal AI assistant that runs entirely through GitHub Issues and Actions. Like [OpenClaw](https://github.com/openclaw/openclaw), but no servers or extra infrastructure.

> **Origin**: This project started as a fork of [SawyerHood/gitclaw](https://github.com/SawyerHood/gitclaw) — even Crunch's name comes from there. It's since grown into its own thing.

Powered by [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli). Every issue becomes a chat thread with an AI agent — but more than that, the agent can **write new skills for itself**, update its own instructions, and commit them back to the repo. Future sessions inherit everything it commits. The assistant evolves as you use it.

Conversation history is committed to git, giving the agent long-term memory across sessions. It maintains a `memory.log`, a user profile, and can grow its own capabilities over time.

## How it works

1. **Create an issue** → the agent processes your request and replies as a comment.
2. **Comment on the issue** → the agent resumes the same session with full prior context.
3. **Everything is committed** → sessions, memory, and any file changes are pushed after every turn.
4. **The agent can extend itself** → it can write new skills, update `AGENTS.md`, and commit them so future sessions are smarter.

The agent reacts with 👀 while working and removes it when done.

### Repo as storage

All state lives in the repo:

```
AGENTS.md                   # agent identity + behavioral instructions (auto-loaded)
memory.log                  # append-only log of facts across all sessions
state/
  user.md                   # user profile (name, preferences)
  issues/
    1.json                  # maps issue #1 -> its Copilot CLI session ID
  copilot/
    sessions/
      <id>/                 # full session context for issue #1
.github/
  skills/
    bootstrap/SKILL.md      # first-run identity bootstrap
    write-skill/SKILL.md    # meta-skill: how to create new skills
    remember/SKILL.md       # how to write to memory.log
    <anything>/SKILL.md     # skills the agent writes for itself over time
```

Since everything is in git, it survives across ephemeral runners and is fully version-controlled.

## Setup

1. **Fork this repo**
2. **Create a fine-grained PAT** - go to **Settings → Developer settings → Personal access tokens → Fine-grained tokens** and create a token with the **Copilot Requests** permission. (Requires an active GitHub Copilot subscription — available on all plans.)
3. **Add the PAT as a secret** - go to your fork's **Settings → Secrets and variables → Actions** and create a secret named `COPILOT_PAT`.
4. **Hatch the agent** - open an issue titled anything (e.g. "Hello") and add the **`hatch`** label. The agent will introduce itself, ask about you, and write its own identity into the repo.
5. **Use it** - every subsequent issue is a task or conversation. The agent remembers everything across sessions.

## Security

The workflow only responds to repository **owners, members, and collaborators**. Random users cannot trigger the agent on public repos.

If you plan to use copilotclaw for anything private, **make the repo private**. Public repos mean your conversation history is visible to everyone, but get generous GitHub Actions usage.

## Configuration

Everything lives in `.github/workflows/agent.yml` — no separate scripts. Common tweaks:

- **Model:** Add `--model MODEL` to the `copilot` invocation in the **Run agent** step (e.g. `--model claude-sonnet-4-5`).
- **Tools:** Restrict with `--available-tools read,grep,glob` for read-only analysis.
- **Reasoning:** Add `--experimental` and set `reasoning_effort` in `.copilot/settings.json`.
- **Trigger:** Adjust the `on:` block to filter by labels, assignees, etc.
- **AGENTS.md:** Already loaded automatically as custom instructions for the agent.

## Heartbeat

The agent runs on a **30-minute schedule** via `.github/workflows/heartbeat.yml`. Every 30 minutes it:

1. Reads recent memory and scans open `priority/now` issues
2. Checks CI health
3. Posts a diary entry to the pinned [🫀 Heartbeat Diary](../../issues/10) issue
4. Writes anything notable to `memory.log` and commits it

This makes the agent *proactive* — not just reactive to your comments. The `HEARTBEAT.md` file is its checklist.

### Roadmap

| Milestone | Status | What it unlocks |
|-----------|--------|-----------------|
| v0.1 — Heartbeat Alive | ✅ Done | Scheduled runs, diary, memory |
| v0.2 — Issue Spawning | 🔜 Next | Crunch creates its own tasks |
| v0.3 — Autonomous Skills | 🔮 Planned | Crunch works `crunch/build` issues alone |
| v0.4 — Email + Comms | 📬 Planned | Daily digest email to you |

## Acknowledgments

Forked from [gitclaw](https://github.com/schuerstedt/gitclaw) by [@schuerstedt](https://github.com/schuerstedt) and rebuilt as a Copilot-native agent — now living as [copilotclaw](https://github.com/schuerstedt/copilotclaw). Original project built on top of [pi-mono](https://github.com/badlogic/pi-mono) by [Mario Zechner](https://github.com/badlogic). Now powered by [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli).
