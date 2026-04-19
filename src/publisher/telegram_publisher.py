"""Send generated posts and paper summaries via Telegram bot."""

from __future__ import annotations

import logging

import httpx

from src.core import config

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram(text: str, parse_mode: str = "HTML") -> bool:
    """Send a message via Telegram bot API.

    Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env.
    """
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        logger.warning("Telegram not configured (set TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)")
        return False

    try:
        resp = httpx.post(
            TELEGRAM_API.format(token=token),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            logger.info("Telegram message sent")
            return True
        logger.error("Telegram API error: %s", resp.text[:200])
        return False
    except Exception as e:
        logger.error("Telegram send failed: %s", e)
        return False


def send_posts_telegram(posts: list[dict]) -> bool:
    """Send trend posts as individual Telegram messages."""
    if not posts:
        return False

    success = 0
    for i, post in enumerate(posts, 1):
        domain = post.get("domain", "").upper()
        trend = post.get("trend_title", "")
        hashtags = " ".join(post.get("hashtags", []))
        url = post.get("url", "")

        lines = [
            f"<b>[{i}/{len(posts)}] {domain}</b> — {_escape(trend)}",
            "",
            _escape(post["content"]),
        ]
        if hashtags:
            lines.append(f"\n<i>{_escape(hashtags)}</i>")
        if url:
            lines.append(f'\n<a href="{url}">Source</a>')

        if send_telegram("\n".join(lines)):
            success += 1

    return success > 0


def send_papers_telegram(papers: list[tuple]) -> bool:
    """Send paper summaries as individual Telegram messages.

    Args:
        papers: list of (paper, summary) tuples where paper is an ArxivPaper
    """
    if not papers:
        return False

    success = 0
    for i, (paper, summary) in enumerate(papers, 1):
        tag = "AGENTIC" if paper.is_agentic else "AI"
        score = paper.interest_score
        authors = ", ".join(paper.authors[:3])

        lines = [
            f"<b>[{i}/{len(papers)}] {tag} — Score: {score:.1f}/18</b>",
            "",
            f"<b>{_escape(paper.title)}</b>",
            f"<i>{_escape(authors)}</i>",
            "",
            _escape(summary),
            "",
            f'<a href="{paper.url}">Paper</a>',
        ]
        if paper.pdf_url:
            lines[-1] += f' | <a href="{paper.pdf_url}">PDF</a>'

        if send_telegram("\n".join(lines)):
            success += 1

    return success > 0


def _escape(text: str) -> str:
    """Escape HTML special chars for Telegram."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
