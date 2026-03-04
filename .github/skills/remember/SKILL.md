---
name: remember
description: Store an important fact, preference, or decision in memory.log for future sessions. Invoke when the user says "remember this", "remember:", or when you learn something that future-you should know.
allowed-tools: ["shell(echo:*)", "shell(date:*)", "shell(bash:*)", "shell(git:*)"]
---

# Remember

Append a memory to `memory.log` so future sessions know this fact.

## Format

```
[YYYY-MM-DD HH:MM] One-line memory entry — atomic, grep-friendly.
```

## Write it

```bash
echo "[$(date -u '+%Y-%m-%d %H:%M')] THE FACT TO REMEMBER." >> memory.log
git add memory.log
git commit -m "memory: [short description]"
git push origin main
```

## Good memory entries look like

```
[2026-03-04 14:22] User prefers concise responses, no bullet-point overload.
[2026-03-04 14:23] Repo uses Copilot CLI with COPILOT_PAT secret for auth.
[2026-03-04 15:01] User's name is Alex. Goes by Alex, not their GitHub handle.
[2026-03-05 09:14] User building negotiation101.html as first real test of gitclaw.
```

## Search memory

```bash
rg -i "search term" memory.log 2>/dev/null
tail -30 memory.log 2>/dev/null
```

## Bad memory entries

- Things already documented in README or other files
- Transient task details (what you did this session)
- Vague entries like "user wants good code"
