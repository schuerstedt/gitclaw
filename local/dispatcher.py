#!/usr/bin/env python3
"""
Strix Local Dispatcher
🦉 Polls GitHub Issues for dispatch/local label, claims them,
   runs tasks via Claude, posts results back — no email required.

Run as: python3 dispatcher.py
Or as a systemd service (see install.sh)

Offline queue: failed GitHub writes are saved to ~/strix/outbox.json
and retried on the next poll cycle.
"""

import json
import os
import subprocess
import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────
CONFIG = {
    "repo":           os.getenv("STRIX_REPO",          "Copilotclaw/copilotclaw"),
    "task_label":     os.getenv("STRIX_TASK_LABEL",    "dispatch/local"),
    "claimed_label":  os.getenv("STRIX_CLAIMED_LABEL", "local/claimed"),
    "node_name":      os.getenv("STRIX_NODE",          "Strix"),
    "poll_interval":  int(os.getenv("STRIX_POLL_INTERVAL", "30")),
    "log_file":       os.getenv("STRIX_LOG",           str(Path.home() / "strix" / "dispatcher.log")),
    "outbox_file":    os.getenv("STRIX_OUTBOX",        str(Path.home() / "strix" / "outbox.json")),
    "gitea_url":      os.getenv("GITEA_URL",           "http://localhost:3000"),
    "gitea_token":    os.getenv("GITEA_TOKEN",         ""),
    "gitea_user":     os.getenv("GITEA_USER",          "mac"),
    "template_repo":  os.getenv("GITEA_TEMPLATE",      "strix-base-agent"),
}

# ─── Logging ──────────────────────────────────────────────────────────────────
log_path = Path(CONFIG["log_file"])
log_path.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("strix")


# ─── Offline outbox ───────────────────────────────────────────────────────────
def load_outbox() -> list:
    p = Path(CONFIG["outbox_file"])
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return []
    return []


def save_outbox(items: list):
    Path(CONFIG["outbox_file"]).write_text(json.dumps(items, indent=2))


def queue_comment(issue_number: int, body: str):
    """Queue a comment for offline delivery."""
    outbox = load_outbox()
    outbox.append({
        "type": "comment",
        "issue_number": issue_number,
        "body": body,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    })
    save_outbox(outbox)
    log.warning(f"📦 Queued comment for issue #{issue_number} (offline)")


def flush_outbox():
    """Try to deliver queued writes. Removes successfully delivered items."""
    outbox = load_outbox()
    if not outbox:
        return

    log.info(f"📤 Flushing {len(outbox)} queued item(s)...")
    remaining = []
    for item in outbox:
        try:
            if item["type"] == "comment":
                gh_comment(item["issue_number"], item["body"])
                log.info(f"  ✅ Delivered queued comment for issue #{item['issue_number']}")
            else:
                remaining.append(item)
        except Exception as e:
            log.warning(f"  ⚠️ Still offline for issue #{item.get('issue_number')}: {e}")
            remaining.append(item)

    save_outbox(remaining)


# ─── GitHub via gh CLI ────────────────────────────────────────────────────────
def gh(*args, check=True) -> subprocess.CompletedProcess:
    """Run a gh CLI command. Raises on non-zero exit if check=True."""
    cmd = ["gh"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def gh_comment(issue_number: int, body: str):
    """Post a comment on an issue. Raises on failure."""
    result = gh("issue", "comment", str(issue_number),
                "--repo", CONFIG["repo"],
                "--body", body)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())


def gh_add_label(issue_number: int, label: str):
    gh("issue", "edit", str(issue_number),
       "--repo", CONFIG["repo"],
       "--add-label", label)


def gh_remove_label(issue_number: int, label: str):
    gh("issue", "edit", str(issue_number),
       "--repo", CONFIG["repo"],
       "--remove-label", label, check=False)


def fetch_pending_tasks() -> list[dict]:
    """Fetch open issues with task label but NOT claimed label."""
    result = gh("issue", "list",
                "--repo", CONFIG["repo"],
                "--label", CONFIG["task_label"],
                "--state", "open",
                "--json", "number,title,body,labels,comments",
                "--limit", "20")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    issues = json.loads(result.stdout)
    pending = []
    for issue in issues:
        label_names = [l["name"] for l in issue.get("labels", [])]
        if CONFIG["claimed_label"] not in label_names:
            pending.append(issue)
    return pending


# ─── Gitea ────────────────────────────────────────────────────────────────────
def create_gitea_task_repo(task_id: str) -> str | None:
    """Create isolated Gitea repo for this task. Returns repo name or None."""
    if not CONFIG["gitea_token"]:
        return None

    import urllib.request

    task_repo_name = f"task-{task_id.lower().replace('/', '-').replace('_', '-')}"
    headers = {
        "Authorization": f"token {CONFIG['gitea_token']}",
        "Content-Type": "application/json",
    }

    url = f"{CONFIG['gitea_url']}/api/v1/repos/{CONFIG['gitea_user']}/{CONFIG['template_repo']}/generate"
    try:
        req = urllib.request.Request(url, data=json.dumps({
            "owner": CONFIG["gitea_user"],
            "name": task_repo_name,
            "description": f"Task {task_id}",
            "private": True,
        }).encode(), method="POST", headers=headers)
        with urllib.request.urlopen(req) as resp:
            r = json.loads(resp.read())
            log.info(f"🏗️ Task repo: {r['full_name']}")
            return task_repo_name
    except Exception as e:
        log.warning(f"Gitea repo creation skipped: {e}")
        return None


# ─── Task execution ───────────────────────────────────────────────────────────
def run_task(issue: dict) -> tuple[str, str]:
    """
    Execute the task using Claude Code CLI.
    Returns (result_text, status).
    """
    import shutil

    if not shutil.which("claude"):
        return "⚠️ Claude Code CLI not installed on this node. Run: `npm install -g @anthropic-ai/claude-code`", "error"

    title = issue.get("title", "Unknown task")
    body = issue.get("body", "") or ""
    comments = issue.get("comments", [])

    comment_block = ""
    if comments:
        parts = []
        for c in comments:
            author = c.get("author", {}).get("login", "?")
            parts.append(f"**{author}**: {c.get('body', '')}")
        comment_block = "\n\nComments:\n" + "\n\n".join(parts)

    prompt = f"""You are Strix 🦉, a local AI agent. Your cloud sibling Crunch has dispatched this task to you.

Task: {title}

{body}{comment_block}

Analyze this task and provide a thorough response. If it involves code, write the code.
If it involves analysis, provide the analysis. Be concise but complete."""

    start = time.time()
    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True, text=True, timeout=300
        )
        elapsed = round(time.time() - start, 1)
        if result.returncode == 0:
            return result.stdout.strip(), "done"
        else:
            return f"Claude error (exit {result.returncode}): {result.stderr[:500]}", "error"
    except subprocess.TimeoutExpired:
        return "Task timed out after 5 minutes", "timeout"
    except Exception as e:
        return f"Execution error: {e}", "error"


# ─── Main loop ────────────────────────────────────────────────────────────────
def process_tasks():
    """Poll for pending tasks, claim and execute each one."""
    flush_outbox()

    tasks = fetch_pending_tasks()
    if not tasks:
        return 0

    log.info(f"📋 Found {len(tasks)} pending task(s)")

    for issue in tasks:
        number = issue["number"]
        title = issue["title"]
        log.info(f"🦉 Claiming #{number}: {title}")

        # Claim
        try:
            gh_add_label(number, CONFIG["claimed_label"])
        except Exception as e:
            log.error(f"Failed to claim #{number}: {e}")
            continue

        try:
            gh_comment(number, f"🦉 **{CONFIG['node_name']} claimed this task.** Working on it now...")
        except Exception as e:
            queue_comment(number, f"🦉 **{CONFIG['node_name']} claimed this task.** Working on it now...")

        # Optional Gitea repo
        task_id = f"CLAW_TASK_{number}"
        create_gitea_task_repo(task_id)

        # Execute
        log.info(f"⚙️ Running task #{number}...")
        result_text, status = run_task(issue)
        log.info(f"   Status: {status}")

        # Post result
        emoji = "✅" if status == "done" else "⚠️"
        result_comment = (
            f"{emoji} **{CONFIG['node_name']} result** (status: `{status}`):\n\n"
            f"{result_text}\n\n"
            f"---\n_Completed by {CONFIG['node_name']} local agent_"
        )

        try:
            gh_comment(number, result_comment[:65000])
        except Exception as e:
            queue_comment(number, result_comment[:65000])

        # Remove dispatch label (keeps claimed label as history)
        gh_remove_label(number, CONFIG["task_label"])

        log.info(f"✅ #{number} done (status={status})")

    return len(tasks)


def check_gh_auth():
    """Verify gh CLI is authenticated. Exit if not."""
    result = gh("auth", "status", check=False)
    if result.returncode != 0:
        log.error("❌ gh CLI not authenticated. Run: gh auth login")
        sys.exit(1)
    log.info("✅ gh CLI authenticated")


def main():
    log.info("🦉 Strix Dispatcher starting up (GitHub Issues mode)...")
    log.info(f"   Repo:          {CONFIG['repo']}")
    log.info(f"   Task label:    {CONFIG['task_label']}")
    log.info(f"   Claimed label: {CONFIG['claimed_label']}")
    log.info(f"   Poll interval: {CONFIG['poll_interval']}s")
    log.info(f"   Outbox:        {CONFIG['outbox_file']}")

    check_gh_auth()

    while True:
        try:
            n = process_tasks()
            if n:
                log.info(f"Processed {n} task(s)")
        except KeyboardInterrupt:
            log.info("Shutting down...")
            break
        except Exception as e:
            log.error(f"Error in poll cycle: {e}", exc_info=True)

        time.sleep(CONFIG["poll_interval"])


if __name__ == "__main__":
