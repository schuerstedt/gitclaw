#!/usr/bin/env python3
"""
Strix Local Dispatcher
🦉 Polls IMAP inbox, verifies PGP signatures from Crunch,
   triggers Gitea task repos, sends results back.

Run as: python3 dispatcher.py
Or as a systemd service (see install.sh)
"""

import gnupg
import imaplib
import smtplib
import email as email_lib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────
CONFIG = {
    "imap_host":        os.getenv("STRIX_IMAP_HOST",    "mx2f20.netcup.net"),
    "imap_port":        int(os.getenv("STRIX_IMAP_PORT", "993")),
    "smtp_host":        os.getenv("STRIX_SMTP_HOST",    "mx2f20.netcup.net"),
    "smtp_port":        int(os.getenv("STRIX_SMTP_PORT", "465")),
    "local_email":      os.getenv("STRIX_LOCAL_EMAIL",  "crunchlocal.agent@aigege.de"),
    "local_password":   os.getenv("STRIX_LOCAL_PASSWORD", ""),
    "cloud_email":      os.getenv("STRIX_CLOUD_EMAIL",  "crunchcloud.agent@aigege.de"),
    "crunch_fingerprint": os.getenv("CRUNCH_GPG_FINGERPRINT", ""),
    "gitea_url":        os.getenv("GITEA_URL",          "http://localhost:3000"),
    "gitea_token":      os.getenv("GITEA_TOKEN",        ""),
    "gitea_user":       os.getenv("GITEA_USER",         "mac"),
    "template_repo":    os.getenv("GITEA_TEMPLATE",     "strix-base-agent"),
    "poll_interval":    int(os.getenv("STRIX_POLL_INTERVAL", "30")),
    "gnupghome":        os.getenv("GNUPGHOME",          str(Path.home() / ".gnupg")),
    "log_file":         os.getenv("STRIX_LOG",          str(Path.home() / "strix" / "dispatcher.log")),
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


# ─── GPG setup ────────────────────────────────────────────────────────────────
gpg = gnupg.GPG(gnupghome=CONFIG["gnupghome"])


def verify_crunch_signature(signed_text: str) -> tuple[bool, dict]:
    """Verify a clearsigned message from Crunch. Returns (valid, payload_dict)."""
    verify = gpg.verify(signed_text)
    if not verify.valid:
        log.warning(f"Signature invalid: {verify.status}")
        return False, {}

    crunch_fp = CONFIG["crunch_fingerprint"].upper().replace(" ", "")
    msg_fp = (verify.fingerprint or "").upper()
    if crunch_fp and not msg_fp.endswith(crunch_fp[-16:]):
        log.warning(f"Signed by unknown key {msg_fp}, expected {crunch_fp}")
        return False, {}

    # Extract JSON from clearsigned block
    try:
        lines = signed_text.split('\n')
        json_start = next(i for i, l in enumerate(lines) if l.strip().startswith('{'))
        json_end = next(i for i, l in enumerate(lines) if '-----BEGIN PGP SIGNATURE-----' in l)
        payload = json.loads('\n'.join(lines[json_start:json_end]))
        return True, payload
    except Exception as e:
        log.error(f"Could not parse payload JSON: {e}")
        return True, {"raw": signed_text}


def sign_result(result_json: str) -> str:
    """Sign result payload with Strix's private key."""
    signed = gpg.sign(result_json, clearsign=True)
    if not signed:
        raise RuntimeError("Strix GPG signing failed")
    return str(signed)


# ─── Email ────────────────────────────────────────────────────────────────────
def send_result(task_id: str, issue_number: int, result: str, status: str, model_used: str, elapsed: float):
    """Send signed result back to Crunch."""
    payload = {
        "task_id": task_id,
        "issue_number": issue_number,
        "result": result,
        "status": status,
        "model_used": model_used,
        "elapsed_seconds": round(elapsed, 1),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    payload_json = json.dumps(payload, indent=2)
    signed = sign_result(payload_json)

    msg = MIMEMultipart()
    msg['From'] = CONFIG["local_email"]
    msg['To'] = CONFIG["cloud_email"]
    msg['Subject'] = f"CLAW_RESULT: {task_id} {status}"
    msg['X-CLAW-Task-ID'] = task_id
    msg.attach(MIMEText(signed, 'plain'))

    with smtplib.SMTP_SSL(CONFIG["smtp_host"], CONFIG["smtp_port"]) as server:
        server.login(CONFIG["local_email"], CONFIG["local_password"])
        server.send_message(msg)

    log.info(f"✅ Result sent for {task_id} (status={status})")


def send_claimed(task_id: str, reply_to_msg_id: str = None):
    """Send CLAIMED reply to prevent other nodes from picking up the same task."""
    msg = MIMEText(f"CLAIMED: {task_id} [NODE: STRIX_01]\nTimestamp: {datetime.now(timezone.utc).isoformat()}")
    msg['From'] = CONFIG["local_email"]
    msg['To'] = CONFIG["cloud_email"]
    msg['Subject'] = f"CLAW_CLAIMED: {task_id}"

    with smtplib.SMTP_SSL(CONFIG["smtp_host"], CONFIG["smtp_port"]) as server:
        server.login(CONFIG["local_email"], CONFIG["local_password"])
        server.send_message(msg)


# ─── Gitea ────────────────────────────────────────────────────────────────────
def create_gitea_task_repo(task_id: str) -> str:
    """Create isolated Gitea repo for this task from template. Returns repo name."""
    import urllib.request, urllib.error

    task_repo_name = f"task-{task_id.lower().replace('/', '-')}"
    headers = {
        "Authorization": f"token {CONFIG['gitea_token']}",
        "Content-Type": "application/json",
    }
    data = json.dumps({
        "owner": CONFIG["gitea_user"],
        "name": task_repo_name,
        "description": f"Auto-created task repo for {task_id}",
        "private": True,
        "auto_init": True,
    }).encode()

    # Try to generate from template first
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
            log.info(f"Created task repo from template: {r['full_name']}")
            return task_repo_name
    except Exception as e:
        log.warning(f"Template clone failed ({e}), creating bare repo")
        req = urllib.request.Request(
            f"{CONFIG['gitea_url']}/api/v1/user/repos",
            data=data, method="POST", headers=headers
        )
        with urllib.request.urlopen(req) as resp:
            r = json.loads(resp.read())
            log.info(f"Created bare task repo: {r['full_name']}")
            return task_repo_name


def trigger_task_via_claude(task_id: str, payload: dict) -> tuple[str, str]:
    """
    Execute the task using Claude Code CLI.
    Returns (result_text, status).
    """
    import shutil

    if not shutil.which("claude"):
        return "Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code", "error"

    issue_title = payload.get("issue_title", "Unknown task")
    issue_body = payload.get("issue_body", "")

    prompt = f"""You are Strix 🦉, a local AI agent. Your cloud sibling Crunch has dispatched this task to you.

Task: {issue_title}

Details:
{issue_body}

Analyze this task and provide a thorough response. If it involves code, write the code. If it involves analysis, provide the analysis. Be concise but complete."""

    start = time.time()
    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True, text=True, timeout=300
        )
        elapsed = time.time() - start
        if result.returncode == 0:
            return result.stdout.strip(), "done"
        else:
            return f"Claude error: {result.stderr[:500]}", "error"
    except subprocess.TimeoutExpired:
        return "Task timed out after 5 minutes", "timeout"
    except Exception as e:
        return f"Execution error: {e}", "error"


# ─── Main loop ────────────────────────────────────────────────────────────────
def process_inbox():
    """Connect to IMAP, find CLAW_TASK emails, process them."""
    imap = imaplib.IMAP4_SSL(CONFIG["imap_host"], CONFIG["imap_port"])
    imap.login(CONFIG["local_email"], CONFIG["local_password"])
    imap.select("INBOX")

    _, msg_ids = imap.search(None, 'SUBJECT "CLAW_TASK:" UNSEEN')
    tasks = msg_ids[0].split()

    if not tasks:
        imap.logout()
        return 0

    log.info(f"📬 Found {len(tasks)} new task(s)")

    for mid in tasks:
        _, msg_data = imap.fetch(mid, "(RFC822)")
        msg = email_lib.message_from_bytes(msg_data[0][1])
        subject = msg.get("Subject", "")

        # Parse task ID from subject: "CLAW_TASK: 42 Issue title here"
        m = re.search(r'CLAW_TASK:\s*(GH-\d+|\d+)', subject)
        if not m:
            log.warning(f"Cannot parse task ID from: {subject}")
            imap.store(mid, '+FLAGS', '\\Seen')
            continue

        task_id = m.group(1)
        if not task_id.startswith("GH-"):
            task_id = f"GH-{task_id}"

        log.info(f"📋 Processing {task_id}: {subject}")

        # Get body
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
        else:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

        # Verify Crunch's signature
        valid, payload = verify_crunch_signature(body)
        if not valid:
            log.error(f"❌ Signature verification failed for {task_id} — skipping")
            imap.store(mid, '+FLAGS', '\\Seen')
            continue

        # Send CLAIMED reply
        send_claimed(task_id)

        # Create isolated Gitea repo for this task
        if CONFIG["gitea_token"]:
            try:
                repo_name = create_gitea_task_repo(task_id)
                log.info(f"🏗️ Task repo ready: {CONFIG['gitea_url']}/{CONFIG['gitea_user']}/{repo_name}")
            except Exception as e:
                log.warning(f"Gitea repo creation failed: {e}")

        # Execute with Claude
        issue_number = payload.get("issue_number", 0)
        result_text, status = trigger_task_via_claude(task_id, payload)
        elapsed = time.time()  # rough

        # Send result back
        send_result(
            task_id=task_id,
            issue_number=issue_number,
            result=result_text,
            status=status,
            model_used="claude-code-cli",
            elapsed=0.0,
        )

        # Mark email as read
        imap.store(mid, '+FLAGS', '\\Seen')
        log.info(f"✅ {task_id} completed (status={status})")

    imap.logout()
    return len(tasks)


def main():
    log.info("🦉 Strix Dispatcher starting up...")
    log.info(f"   IMAP: {CONFIG['imap_host']}:{CONFIG['imap_port']}")
    log.info(f"   Local email: {CONFIG['local_email']}")
    log.info(f"   Poll interval: {CONFIG['poll_interval']}s")
    log.info(f"   Gitea: {CONFIG['gitea_url']}")

    if not CONFIG["local_password"]:
        log.error("❌ STRIX_LOCAL_PASSWORD not set — export it before running")
        sys.exit(1)

    while True:
        try:
            n = process_inbox()
            if n:
                log.info(f"Processed {n} task(s)")
        except KeyboardInterrupt:
            log.info("Shutting down...")
            break
        except Exception as e:
            log.error(f"Error in poll cycle: {e}", exc_info=True)

        time.sleep(CONFIG["poll_interval"])


if __name__ == "__main__":
    main()
