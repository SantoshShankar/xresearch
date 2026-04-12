"""Send generated posts via iMessage using macOS AppleScript."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


def send_imessage(recipient: str, message: str) -> bool:
    """Send an iMessage to a phone number or Apple ID.

    Args:
        recipient: Phone number (e.g. +1234567890) or Apple ID email
        message: The message text to send
    """
    # Escape quotes and backslashes for AppleScript
    escaped = message.replace("\\", "\\\\").replace('"', '\\"')

    script = f'''
    tell application "Messages"
        set targetService to 1st account whose service type = iMessage
        set targetBuddy to participant "{recipient}" of targetService
        send "{escaped}" to targetBuddy
    end tell
    '''

    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        logger.info("iMessage sent to %s", recipient)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("iMessage failed: %s", e.stderr)
        return False
    except subprocess.TimeoutExpired:
        logger.error("iMessage send timed out")
        return False


def send_posts_via_imessage(recipient: str, posts: list[dict]) -> int:
    """Send each post as a separate iMessage.

    Args:
        recipient: Phone number or Apple ID
        posts: List of dicts with 'content', 'hashtags', 'domain', 'trend_title', 'url'

    Returns:
        Number of messages successfully sent
    """
    if not posts:
        return 0

    sent = 0
    total = len(posts)

    for i, post in enumerate(posts, 1):
        domain = post.get("domain", "").upper()
        lines = [f"[{i}/{total}] {domain}", ""]
        lines.append(post["content"])
        if post.get("hashtags"):
            lines.append("")
            lines.append(" ".join(post["hashtags"]))
        url = post.get("url", "")
        if url:
            lines.append("")
            lines.append(f"🔗 {url}")
        lines.append(f"\n📌 {post.get('trend_title', '')[:60]}")

        message = "\n".join(lines)
        if send_imessage(recipient, message):
            sent += 1

    return sent
