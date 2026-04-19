"""Send generated posts and paper summaries via email (Gmail SMTP)."""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.core import config

logger = logging.getLogger(__name__)


def send_email(subject: str, body_html: str, body_text: str = "") -> bool:
    """Send an email via Gmail SMTP.

    Requires EMAIL_SENDER, EMAIL_APP_PASSWORD, and EMAIL_RECIPIENT in .env.
    For Gmail: generate an app password at https://myaccount.google.com/apppasswords
    """
    sender = config.EMAIL_SENDER
    password = config.EMAIL_APP_PASSWORD
    recipient = config.EMAIL_RECIPIENT

    if not all([sender, password, recipient]):
        logger.warning("Email not configured (set EMAIL_SENDER, EMAIL_APP_PASSWORD, EMAIL_RECIPIENT)")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    if body_text:
        msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        logger.info("Email sent to %s: %s", recipient, subject)
        return True
    except Exception as e:
        logger.error("Email failed: %s", e)
        return False


def send_posts_email(posts: list[dict]) -> bool:
    """Send trend posts as a single digest email."""
    if not posts:
        return False

    items = []
    for i, post in enumerate(posts, 1):
        domain = post.get("domain", "").upper()
        content = post["content"]
        hashtags = " ".join(post.get("hashtags", []))
        url = post.get("url", "")
        trend = post.get("trend_title", "")

        items.append(f"""
        <div style="margin-bottom:24px;padding:16px;background:#1a1a2e;border-radius:8px;border-left:3px solid {'#4fc3f7' if 'ai' in domain.lower() else '#66bb6a'};">
            <div style="color:#888;font-size:12px;margin-bottom:8px;">[{i}/{len(posts)}] {domain} — {trend}</div>
            <div style="color:#e0e0e0;font-size:15px;line-height:1.5;">{content}</div>
            <div style="color:#4fc3f7;font-size:13px;margin-top:8px;">{hashtags}</div>
            {'<div style="margin-top:8px;"><a href="' + url + '" style="color:#4fc3f7;">' + url + '</a></div>' if url else ''}
        </div>""")

    html = f"""
    <div style="font-family:-apple-system,sans-serif;max-width:600px;margin:0 auto;background:#0d0d1a;padding:24px;border-radius:12px;">
        <h2 style="color:#e0e0e0;margin-bottom:20px;">XResearch — Trend Posts</h2>
        {''.join(items)}
    </div>"""

    text = "\n\n".join(
        f"[{i}/{len(posts)}] {p.get('domain','').upper()}\n{p['content']}\n{' '.join(p.get('hashtags',[]))}"
        for i, p in enumerate(posts, 1)
    )

    return send_email("XResearch: Trend Posts", html, text)


def send_papers_email(papers: list[tuple]) -> bool:
    """Send paper summaries as a single digest email.

    Args:
        papers: list of (paper, summary) tuples where paper is an ArxivPaper
    """
    if not papers:
        return False

    items = []
    for i, (paper, summary) in enumerate(papers, 1):
        tag = "AGENTIC" if paper.is_agentic else "AI"
        color = "#ff8a65" if paper.is_agentic else "#4fc3f7"
        score = paper.interest_score
        authors = ", ".join(paper.authors[:3])

        items.append(f"""
        <div style="margin-bottom:24px;padding:16px;background:#1a1a2e;border-radius:8px;border-left:3px solid {color};">
            <div style="color:{color};font-size:12px;margin-bottom:4px;">[{i}/{len(papers)}] {tag} — Score: {score:.1f}/18</div>
            <div style="color:#e0e0e0;font-size:16px;font-weight:600;margin-bottom:6px;">{paper.title}</div>
            <div style="color:#888;font-size:13px;margin-bottom:10px;">{authors}</div>
            <div style="color:#ccc;font-size:14px;line-height:1.6;">{summary}</div>
            <div style="margin-top:10px;">
                <a href="{paper.url}" style="color:#4fc3f7;font-size:13px;">Paper</a>
                {' | <a href="' + paper.pdf_url + '" style="color:#4fc3f7;font-size:13px;">PDF</a>' if paper.pdf_url else ''}
            </div>
        </div>""")

    html = f"""
    <div style="font-family:-apple-system,sans-serif;max-width:600px;margin:0 auto;background:#0d0d1a;padding:24px;border-radius:12px;">
        <h2 style="color:#e0e0e0;margin-bottom:20px;">XResearch — Paper Digest</h2>
        {''.join(items)}
    </div>"""

    text = "\n\n".join(
        f"[{i}/{len(papers)}] {'AGENTIC' if p.is_agentic else 'AI'} ({p.interest_score:.1f})\n{p.title}\n{s}\n{p.url}"
        for i, (p, s) in enumerate(papers, 1)
    )

    return send_email("XResearch: Paper Digest", html, text)
