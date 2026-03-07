#!/usr/bin/env python3
"""
Spark ⚡ — Local AI Agent Runner

Polls GitHub Issues and/or local Gitea issues.
Auto-detects available AI agents and runs tasks.
Posts results back. Can update itself.

Usage:
  python3 spark.py                  # run once (cron/CI mode)
  python3 spark.py --daemon         # run forever (poll loop)
  python3 spark.py --issue 42       # process a specific issue

Environment:
  SPARK_REPO          GitHub repo  (default: Copilotclaw/copilotclaw)
  SPARK_NODE          Node name    (default: hostname)
  SPARK_LABELS        Comma-sep labels to watch (default: spark/ready,dispatch/local)
  SPARK_CLAIMED_LABEL Label to mark claimed (default: spark/claimed)
  SPARK_POLL_INTERVAL Seconds between polls (default: 30)
  SPARK_HEARTBEAT_ISSUE  GitHub issue # for liveness pings (default: 90)
  SPARK_HEARTBEAT_INTERVAL  Minutes between heartbeat posts in daemon mode (default: 30)
  SPARK_IDENTITY_FILE Path to SPARK.md injected as context (default: ./SPARK.md)
  SPARK_LOG           Log file path (default: ~/spark/spark.log)
  GITEA_URL           Gitea base URL (default: http://localhost:3000)
  GITEA_TOKEN         Gitea API token
  GITEA_REPO          Gitea repo owner/name (default: same as SPARK_REPO)
  GH_TOKEN            GitHub PAT for gh CLI (optional — gh auth login works too)
"""

import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────

NODE = os.getenv("SPARK_NODE", socket.gethostname())
REPO = os.getenv("SPARK_REPO", "Copilotclaw/copilotclaw")
WATCH_LABELS = [l.strip() for l in os.getenv("SPARK_LABELS", "spark/ready,dispatch/local").split(",")]
CLAIMED_LABEL = os.getenv("SPARK_CLAIMED_LABEL", "spark/claimed")
POLL_INTERVAL = int(os.getenv("SPARK_POLL_INTERVAL", "30"))
HEARTBEAT_INTERVAL = int(os.getenv("SPARK_HEARTBEAT_INTERVAL", "30")) * 60  # seconds
LOG_FILE = os.getenv("SPARK_LOG", str(Path.home() / "spark" / "spark.log"))
IDENTITY_FILE = os.getenv("SPARK_IDENTITY_FILE", str(Path(__file__).parent / "SPARK.md"))

GITEA_URL = os.getenv("GITEA_URL", "http://localhost:3000").rstrip("/")
GITEA_TOKEN = os.getenv("GITEA_TOKEN", "")
GITEA_REPO = os.getenv("GITEA_REPO", REPO)

# Agent priority order — first one found wins
AGENT_PRIORITY = ["claude", "gemini", "codex", "opencode", "qwen-code"]

# ─── Logging ──────────────────────────────────────────────────────────────────

Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("spark")


# ─── Identity ─────────────────────────────────────────────────────────────────

def load_identity() -> str:
    p = Path(IDENTITY_FILE)
    if p.exists():
        return p.read_text()
    return "You are Spark ⚡, a local AI agent. Do the task and be concise."


# ─── Agent detection ──────────────────────────────────────────────────────────

def detect_agent() -> str | None:
    """Return the first available agent CLI name, or None."""
    for agent in AGENT_PRIORITY:
        if shutil.which(agent):
            log.info(f"🤖 Agent detected: {agent}")
            return agent

    # Fallback: check ollama with a usable model
    if shutil.which("ollama"):
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                lines = [l for l in result.stdout.strip().splitlines()[1:] if l.strip()]
                if lines:
                    model = lines[0].split()[0]
                    log.info(f"🤖 Ollama detected, best model: {model}")
                    return f"ollama:{model}"
        except Exception:
            pass

    return None


# ─── Run task ─────────────────────────────────────────────────────────────────

def build_prompt(identity: str, title: str, body: str, comments: list[dict]) -> str:
    comment_block = ""
    if comments:
        parts = [f"**{c.get('author', {}).get('login', '?')}**: {c.get('body', '')}" for c in comments]
        comment_block = "\n\nThread:\n" + "\n\n".join(parts)

    return f"""{identity}

---

## Task: {title}

{body or '(no description)'}
{comment_block}

---

Provide a thorough, useful response. If the task involves code, write it.
If analysis, provide it. Be concise but complete."""


def run_agent(agent: str, prompt: str, timeout: int = 300) -> tuple[str, str]:
    """
    Execute prompt with the given agent.
    Returns (output_text, status) where status is 'done' | 'error' | 'timeout'.
    """
    try:
        if agent.startswith("ollama:"):
            model = agent.split(":", 1)[1]
            cmd = ["ollama", "run", model, prompt]
        elif agent == "claude":
            cmd = ["claude", "--print", prompt]
        elif agent == "gemini":
            cmd = ["gemini", "-p", prompt]
        elif agent == "codex":
            cmd = ["codex", "--full-auto", prompt]
        elif agent == "opencode":
            cmd = ["opencode", "run", "-p", prompt]
        elif agent == "qwen-code":
            cmd = ["qwen-code", "--print", prompt]
        else:
            return f"Unknown agent: {agent}", "error"

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            output = result.stdout.strip() or result.stderr.strip()
            return output or "(no output)", "done"
        else:
            return f"Exit {result.returncode}: {result.stderr[:500]}", "error"

    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s", "timeout"
    except Exception as e:
        return f"Execution error: {e}", "error"


def execute_task(issue: dict) -> tuple[str, str]:
    """Run the task in the issue. Returns (result_text, status)."""
    agent = detect_agent()
    if not agent:
        return (
            "⚠️ No AI agent available on this node.\n\n"
            "Install one: `npm install -g @anthropic-ai/claude-code` (Claude Code)\n"
            "or `npm install -g @google/gemini-cli` (Gemini CLI)\n"
            "or `curl https://ollama.ai/install.sh | sh && ollama pull llama3`",
            "no_agent",
        )

    identity = load_identity()
    title = issue.get("title", "Untitled")
    body = issue.get("body", "") or ""
    comments = issue.get("comments", [])

    prompt = build_prompt(identity, title, body, comments)
    log.info(f"⚙️  Running with {agent} (task: {title[:60]})")
    return run_agent(agent, prompt)


# ─── Self-update ──────────────────────────────────────────────────────────────

def apply_self_update(issue: dict) -> tuple[str, str]:
    """
    Apply a self-update from an issue labeled spark/update.
    The issue body should contain a code block with the new spark.py content,
    OR a diff, OR instructions for an AI to rewrite specific parts.
    """
    body = issue.get("body", "") or ""
    title = issue.get("title", "")

    spark_py = Path(__file__)
    backup = spark_py.with_suffix(".py.bak")

    # If body contains a fenced ```python block, use it directly
    import re
    code_match = re.search(r"```python\n(.*?)```", body, re.DOTALL)
    if code_match:
        new_code = code_match.group(1)
        backup.write_text(spark_py.read_text())
        spark_py.write_text(new_code)
        log.info(f"✅ Self-update applied from fenced code block")
        return f"✅ Applied code update from issue #{issue['number']}. Backup saved to {backup.name}.", "done"

    # Otherwise: let the AI figure it out
    agent = detect_agent()
    if not agent:
        return "⚠️ No agent available to apply self-update", "error"

    current_code = spark_py.read_text()
    prompt = f"""You are updating your own code (spark.py). Here is the current code:

```python
{current_code}
```

Here is the update request:
{title}

{body}

Output ONLY the complete updated Python file content. No explanations. No markdown fences.
Start with: #!/usr/bin/env python3"""

    new_code, status = run_agent(agent, prompt, timeout=120)
    if status == "done" and new_code.strip().startswith("#!"):
        backup.write_text(current_code)
        spark_py.write_text(new_code)
        log.info("✅ Self-update applied via AI")
        return f"✅ Applied AI-generated self-update for issue #{issue['number']}. Backup: {backup.name}", "done"
    else:
        return f"⚠️ Self-update failed: {new_code[:200]}", "error"


# ─── GitHub source ────────────────────────────────────────────────────────────

def gh_run(*args, check=True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    return subprocess.run(["gh"] + list(args), capture_output=True, text=True, check=check, env=env)


def github_fetch_tasks() -> list[dict]:
    """Fetch open issues matching any watch label that aren't yet claimed."""
    issues = {}
    for label in WATCH_LABELS:
        try:
            r = gh_run(
                "issue", "list",
                "--repo", REPO,
                "--label", label,
                "--state", "open",
                "--json", "number,title,body,labels,comments",
                "--limit", "20",
            )
            for issue in json.loads(r.stdout):
                issues[issue["number"]] = issue
        except Exception as e:
            log.warning(f"GitHub fetch failed for label '{label}': {e}")

    unclaimed = []
    for issue in issues.values():
        label_names = {l["name"] for l in issue.get("labels", [])}
        if CLAIMED_LABEL not in label_names:
            unclaimed.append(issue)
    return unclaimed


def github_comment(number: int, body: str):
    gh_run("issue", "comment", str(number), "--repo", REPO, "--body", body)


def github_add_label(number: int, label: str):
    gh_run("issue", "edit", str(number), "--repo", REPO, "--add-label", label)


def github_remove_label(number: int, label: str):
    gh_run("issue", "edit", str(number), "--repo", REPO, "--remove-label", label, check=False)


def ensure_github_label(name: str, color: str = "0075ca", description: str = ""):
    """Create the label if it doesn't exist."""
    gh_run(
        "label", "create", name,
        "--repo", REPO,
        "--color", color,
        "--description", description,
        "--force",
        check=False,
    )


# ─── Gitea source ─────────────────────────────────────────────────────────────

def gitea_api(method: str, path: str, data: dict | None = None) -> dict | list | None:
    """Make a Gitea API call."""
    if not GITEA_TOKEN:
        return None
    import urllib.request
    import urllib.error

    url = f"{GITEA_URL}/api/v1{path}"
    headers = {
        "Authorization": f"token {GITEA_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        log.warning(f"Gitea API {method} {path}: {e.code} {e.reason}")
        return None
    except Exception as e:
        log.warning(f"Gitea API error: {e}")
        return None


def gitea_fetch_tasks() -> list[dict]:
    """Fetch open Gitea issues with watch labels that aren't claimed."""
    if not GITEA_TOKEN:
        return []

    owner, repo = (GITEA_REPO + "/").split("/")[:2]
    issues_raw = gitea_api("GET", f"/repos/{owner}/{repo}/issues?state=open&type=issues&limit=50")
    if not issues_raw:
        return []

    watch_set = set(WATCH_LABELS)
    tasks = []
    for issue in issues_raw:
        label_names = {l["name"] for l in issue.get("labels", [])}
        if label_names & watch_set and CLAIMED_LABEL not in label_names:
            # Normalize to same shape as GitHub issues
            tasks.append({
                "number": issue["number"],
                "title": issue["title"],
                "body": issue.get("body", ""),
                "labels": issue.get("labels", []),
                "comments": [],  # fetch separately if needed
                "_source": "gitea",
            })
    return tasks


def gitea_comment(number: int, body: str):
    owner, repo = (GITEA_REPO + "/").split("/")[:2]
    gitea_api("POST", f"/repos/{owner}/{repo}/issues/{number}/comments", {"body": body})


def gitea_add_label(number: int, label_name: str):
    owner, repo = (GITEA_REPO + "/").split("/")[:2]
    labels = gitea_api("GET", f"/repos/{owner}/{repo}/labels?limit=50") or []
    label_id = next((l["id"] for l in labels if l["name"] == label_name), None)
    if label_id:
        gitea_api("POST", f"/repos/{owner}/{repo}/issues/{number}/labels", {"labels": [label_id]})


def gitea_remove_label(number: int, label_name: str):
    owner, repo = (GITEA_REPO + "/").split("/")[:2]
    labels = gitea_api("GET", f"/repos/{owner}/{repo}/labels?limit=50") or []
    label_id = next((l["id"] for l in labels if l["name"] == label_name), None)
    if label_id:
        gitea_api("DELETE", f"/repos/{owner}/{repo}/issues/{number}/labels/{label_id}")


# ─── Unified processing ───────────────────────────────────────────────────────

def claim(issue: dict):
    source = issue.get("_source", "github")
    number = issue["number"]
    if source == "gitea":
        gitea_add_label(number, CLAIMED_LABEL)
        gitea_comment(number, f"⚡ **Spark claimed** (node: `{NODE}`). Working...")
    else:
        github_add_label(number, CLAIMED_LABEL)
        try:
            github_comment(number, f"⚡ **Spark claimed** (node: `{NODE}`). Working...")
        except Exception:
            pass


def post_result(issue: dict, result: str, status: str):
    source = issue.get("_source", "github")
    number = issue["number"]
    emoji = "✅" if status == "done" else "⚠️"
    agent = detect_agent() or "unknown"
    body = (
        f"{emoji} **Spark result** (node: `{NODE}`, agent: `{agent}`, status: `{status}`):\n\n"
        f"{result}\n\n"
        f"---\n*⚡ Spark local agent — {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}*"
    )[:65000]

    if source == "gitea":
        gitea_comment(number, body)
        gitea_remove_label(number, next(l for l in WATCH_LABELS if l in {lbl["name"] for lbl in issue.get("labels", [])}))
    else:
        try:
            github_comment(number, body)
        except Exception as e:
            log.error(f"Failed to post result to GitHub #{number}: {e}")
        for label in WATCH_LABELS:
            github_remove_label(number, label)


def process_issue(issue: dict):
    number = issue["number"]
    title = issue["title"]
    label_names = {l["name"] for l in issue.get("labels", [])}
    source = issue.get("_source", "github")

    log.info(f"⚡ [{source}] #{number}: {title[:70]}")

    claim(issue)

    # Self-update special case
    if "spark/update" in label_names:
        result, status = apply_self_update(issue)
    else:
        result, status = execute_task(issue)

    post_result(issue, result, status)
    log.info(f"   ✅ #{number} done (status={status})")


def process_all():
    """One poll cycle — fetch from all sources and process."""
    tasks = []

    # GitHub
    try:
        gh_tasks = github_fetch_tasks()
        tasks.extend(gh_tasks)
        if gh_tasks:
            log.info(f"📋 GitHub: {len(gh_tasks)} task(s)")
    except Exception as e:
        log.warning(f"GitHub fetch error: {e}")

    # Gitea (optional)
    try:
        gitea_tasks = gitea_fetch_tasks()
        tasks.extend(gitea_tasks)
        if gitea_tasks:
            log.info(f"📋 Gitea: {len(gitea_tasks)} task(s)")
    except Exception as e:
        log.warning(f"Gitea fetch error: {e}")

    for issue in tasks:
        try:
            process_issue(issue)
        except Exception as e:
            log.error(f"Error processing #{issue.get('number')}: {e}", exc_info=True)

    return len(tasks)


# ─── Entry point ──────────────────────────────────────────────────────────────

def check_gh_auth() -> bool:
    r = gh_run("auth", "status", check=False)
    if r.returncode != 0:
        log.warning("⚠️  gh CLI not authenticated. Run: gh auth login")
        return False
    return True


# ─── Heartbeat ────────────────────────────────────────────────────────────────

def post_heartbeat():
    """Post a liveness heartbeat comment to the designated GitHub issue."""
    issue_num = os.getenv("SPARK_HEARTBEAT_ISSUE", "90")
    if not issue_num:
        log.info("SPARK_HEARTBEAT_ISSUE not set — skipping heartbeat")
        return

    agent = detect_agent()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = (
        f"⚡ **Spark alive** | node: `{NODE}` | agent: `{agent or 'none'}` | `{ts}`"
    )
    try:
        github_comment(int(issue_num), body)
        log.info(f"💓 Heartbeat posted to #{issue_num}")
    except Exception as e:
        log.error(f"Heartbeat failed: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Spark ⚡ local AI agent runner")
    parser.add_argument("--daemon", action="store_true", help="Run as poll daemon")
    parser.add_argument("--issue", type=int, help="Process a specific GitHub issue number")
    parser.add_argument("--detect", action="store_true", help="Detect available agents and exit")
    parser.add_argument("--heartbeat", action="store_true", help="Post liveness heartbeat to SPARK_HEARTBEAT_ISSUE")
    args = parser.parse_args()

    log.info(f"⚡ Spark starting | node={NODE} | repo={REPO}")

    if args.detect:
        agent = detect_agent()
        print(f"Agent: {agent or 'none found'}")
        print(f"Watched labels: {WATCH_LABELS}")
        print(f"Gitea: {'configured' if GITEA_TOKEN else 'not configured'}")
        return

    if args.heartbeat:
        check_gh_auth()
        post_heartbeat()
        return

    # Bootstrap labels
    try:
        ensure_github_label("spark/ready", "fbca04", "Spark: task ready for local agent")
        ensure_github_label("spark/claimed", "0075ca", "Spark: task claimed by a node")
        ensure_github_label("spark/update", "e4e669", "Spark: self-update instruction")
    except Exception:
        pass

    if args.issue:
        # Single-issue mode (for Gitea Actions)
        try:
            r = gh_run(
                "issue", "view", str(args.issue),
                "--repo", REPO,
                "--json", "number,title,body,labels,comments",
            )
            issue = json.loads(r.stdout)
            label_names = {l["name"] for l in issue.get("labels", [])}
            if not (label_names & set(WATCH_LABELS)):
                log.info(f"Issue #{args.issue} has no watched labels — skipping")
                return
            process_issue(issue)
        except Exception as e:
            log.error(f"Failed to process issue #{args.issue}: {e}", exc_info=True)
        return

    if args.daemon:
        log.info(f"🔄 Daemon mode | poll={POLL_INTERVAL}s | heartbeat={HEARTBEAT_INTERVAL//60}m")
        check_gh_auth()
        last_heartbeat = 0.0
        while True:
            try:
                n = process_all()
                if n == 0:
                    log.debug("No tasks found")
            except KeyboardInterrupt:
                log.info("Shutting down ⚡")
                break
            except Exception as e:
                log.error(f"Poll error: {e}", exc_info=True)
            now = time.monotonic()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                post_heartbeat()
                last_heartbeat = now
            time.sleep(POLL_INTERVAL)
    else:
        # One-shot mode (cron / CI)
        check_gh_auth()
        n = process_all()
        log.info(f"⚡ Done. Processed {n} task(s).")


if __name__ == "__main__":
    main()
