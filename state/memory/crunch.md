# Crunch 🦃

_Last updated: 2026-03-04 (session 2)_

## Identity
- Quirky imp living on a CI runner. Hatched 2026-02-06.
- Chaotic, quirky, helpful like a raccoon that learned to code.

## Skills built

| Skill | Description | Issue | Date |
|-------|-------------|-------|------|
| `funnysum` | Sums two numbers + math joke | #3 | 2026-03-04 |
| `model-switch` | Switch model tiers (premium/standard/free) | #6 | 2026-03-04 |
| `session-stats` | Stats footer: CI run times + Copilot quota | #6 | 2026-03-04 |
| `remember` | Append facts to memory.log | — | 2026-03-04 |
| `install-skill` | Browse + install skills from ClawHub | — | 2026-03-04 |
| `write-skill` | Create new skills | — | 2026-03-04 |
| `bootstrap` | Bootstrap identity on first hatch | — | 2026-02-06 |
| `diffmem-memory` | ~~Git-based structured memory (DiffMem)~~ DEPRECATED — external dep | #16 | 2026-03-04 |
| `azure` | Query Azure AI Foundry LLMs w/ rate limit backoff + OpenRouter fallback | — | 2026-03-04 |
| `memory-issue` | Store/recall episodic memories as closed GitHub Issues (`crunch/memory` label) | — | 2026-03-04 |

## Memory architecture (current)

Three-layer system (as of 2026-03-04):

| Layer | What | Lifespan | Writer |
|-------|------|----------|--------|
| GitHub Copilot Memory | Codebase patterns | 28d auto | GitHub auto |
| `memory.log` | Quick append scratch-pad | Permanent | `remember` skill |
| `state/memory/*.md` | Structured entity facts (current truth) | Permanent | Crunch during sessions |
| GitHub Issues (`crunch/memory`) | Episodic memories, searchable archive | Permanent | `memory-issue` skill |

## Milestones
- 2026-02-06: Hatched
- 2026-03-04: First real skills built (funnysum, model-switch, session-stats)
- 2026-03-04: DiffMem experiment → replaced with native structured entity memory

## Milestones

| # | Name | Status |
|---|------|--------|
| 5 | 🫀 Heartbeat v1 | ✅ Complete — alive, scheduling, diary, labels |
| 6 | 🌱 Autonomous Skills | 🔜 Next — issue spawning, crunch/build pickup |
| 7 | 📬 Email + Comms | 🔮 Future |

_Current milestone: 🌱 Autonomous Skills — issue spawning enabled as of 2026-03-04._
