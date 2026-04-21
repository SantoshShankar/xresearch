"""Generate a static HTML dashboard from history.json for GitHub Pages."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from html import escape
from pathlib import Path

logger = logging.getLogger(__name__)


def _relative_date(iso_str: str) -> tuple[str, str]:
    """Return (relative label, absolute date) from an ISO timestamp."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except Exception:
        return ("Unknown", iso_str)
    now = datetime.now(timezone.utc)
    delta = now - dt
    days = delta.days

    absolute = dt.strftime("%Y-%m-%d %H:%M UTC")
    if days == 0:
        return ("Today", absolute)
    elif days == 1:
        return ("Yesterday", absolute)
    elif days < 7:
        return (f"{days} days ago", absolute)
    else:
        return (f"{days} days ago", absolute)


def _group_by_date(items: list[dict], date_key: str = "sent_at") -> list[tuple[str, str, list[dict]]]:
    """Group items by date, return list of (date_str, relative_label, items) sorted desc."""
    groups: dict[str, list[dict]] = {}
    for item in items:
        try:
            dt = datetime.fromisoformat(item.get(date_key, "").replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
        except Exception:
            date_str = "Unknown"
        groups.setdefault(date_str, []).append(item)

    result = []
    for date_str in sorted(groups.keys(), reverse=True):
        relative, _ = _relative_date(date_str + "T12:00:00+00:00")
        result.append((date_str, relative, groups[date_str]))
    return result


def _border_color(item: dict, is_paper: bool) -> str:
    """Return left border color based on domain/type."""
    if is_paper:
        # Check for agentic papers by looking at title keywords
        title = item.get("title", "").lower()
        if any(kw in title for kw in ["agent", "agentic", "tool use", "planning"]):
            return "#f97316"  # orange for agentic
        return "#3b82f6"  # blue for AI
    domain = item.get("domain", "").lower()
    if domain == "cricket":
        return "#22c55e"  # green
    return "#3b82f6"  # blue for AI


def _render_paper_cards(papers: list[dict]) -> str:
    if not papers:
        return '<p class="empty-msg">No papers in the last 10 days.</p>'

    groups = _group_by_date(papers)
    html_parts = []
    for date_str, relative, items in groups:
        html_parts.append(f'<div class="date-group"><h3 class="date-header" title="{escape(date_str)}">{escape(relative)} &mdash; {escape(date_str)}</h3>')
        for p in items:
            title = escape(p.get("title", "Untitled"))
            score = p.get("score", 0)
            arxiv_id = escape(p.get("arxiv_id", ""))
            sent_at = p.get("sent_at", "")
            _, abs_date = _relative_date(sent_at)
            border = _border_color(p, is_paper=True)

            # Determine tag
            title_lower = p.get("title", "").lower()
            if any(kw in title_lower for kw in ["agent", "agentic", "tool use", "planning"]):
                tag = "AGENTIC"
                tag_class = "tag-agentic"
            else:
                tag = "AI"
                tag_class = "tag-ai"

            paper_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "#"

            html_parts.append(f'''
            <div class="card" style="border-left: 3px solid {border}">
                <div class="card-top">
                    <span class="tag {tag_class}">{tag}</span>
                    <span class="score-badge">{score:.1f}</span>
                    <span class="card-time" title="{escape(abs_date)}">{escape(abs_date)}</span>
                </div>
                <h4 class="card-title"><a href="{escape(paper_url)}" target="_blank">{title}</a></h4>
            </div>''')
        html_parts.append('</div>')
    return "\n".join(html_parts)


def _render_post_cards(posts: list[dict]) -> str:
    if not posts:
        return '<p class="empty-msg">No posts in the last 10 days.</p>'

    groups = _group_by_date(posts)
    html_parts = []
    for date_str, relative, items in groups:
        html_parts.append(f'<div class="date-group"><h3 class="date-header" title="{escape(date_str)}">{escape(relative)} &mdash; {escape(date_str)}</h3>')
        for p in items:
            domain = escape(p.get("domain", "ai").upper())
            domain_lower = p.get("domain", "ai").lower()
            trend_title = escape(p.get("trend_title", ""))
            sent_at = p.get("sent_at", "")
            _, abs_date = _relative_date(sent_at)
            border = _border_color(p, is_paper=False)

            tag_class = "tag-cricket" if domain_lower == "cricket" else "tag-ai"

            html_parts.append(f'''
            <div class="card" style="border-left: 3px solid {border}">
                <div class="card-top">
                    <span class="tag {tag_class}">{domain}</span>
                    <span class="card-time" title="{escape(abs_date)}">{escape(abs_date)}</span>
                </div>
                <p class="card-content">{trend_title}</p>
            </div>''')
        html_parts.append('</div>')
    return "\n".join(html_parts)


def generate_dashboard(history: dict, output_dir: str = "site") -> None:
    """Generate static site/index.html and site/feed.json from history data."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=10)
    cutoff_iso = cutoff.isoformat()

    papers = [p for p in history.get("papers", []) if p.get("sent_at", "") >= cutoff_iso]
    posts = [p for p in history.get("posts", []) if p.get("sent_at", "") >= cutoff_iso]

    updated = now.strftime("%Y-%m-%d %H:%M UTC")

    paper_html = _render_paper_cards(papers)
    post_html = _render_post_cards(posts)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>XResearch</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d0d1a;
            color: #e0e0e0;
            min-height: 100vh;
        }}
        .header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 28px 32px 20px;
            border-bottom: 1px solid #2a2a4a;
            text-align: center;
        }}
        .header h1 {{
            font-size: 28px;
            font-weight: 700;
            color: #fff;
            letter-spacing: -0.5px;
        }}
        .header .updated {{
            color: #666;
            font-size: 13px;
            margin-top: 6px;
        }}
        .main {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 24px 16px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 32px;
        }}
        @media (max-width: 768px) {{
            .main {{
                grid-template-columns: 1fr;
                gap: 24px;
                padding: 16px 12px;
            }}
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            color: #ccc;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid #2a2a4a;
        }}
        .date-group {{
            margin-bottom: 20px;
        }}
        .date-header {{
            font-size: 13px;
            font-weight: 500;
            color: #888;
            margin-bottom: 10px;
            padding-left: 4px;
        }}
        .card {{
            background: #1a1a2e;
            border: 1px solid #2a2a4a;
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 10px;
            transition: border-color 0.2s;
        }}
        .card:hover {{
            border-color: #444;
        }}
        .card-top {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }}
        .tag {{
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .tag-ai {{
            background: #1e3a5f;
            color: #60a5fa;
        }}
        .tag-cricket {{
            background: #1a3a1e;
            color: #86efac;
        }}
        .tag-agentic {{
            background: #3d2a0f;
            color: #f97316;
        }}
        .score-badge {{
            background: #2d2a0f;
            color: #fbbf24;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
        }}
        .card-time {{
            color: #555;
            font-size: 11px;
            margin-left: auto;
        }}
        .card-title {{
            font-size: 14px;
            font-weight: 600;
            line-height: 1.4;
        }}
        .card-title a {{
            color: #d0d0d0;
            text-decoration: none;
        }}
        .card-title a:hover {{
            color: #60a5fa;
            text-decoration: underline;
        }}
        .card-content {{
            font-size: 14px;
            line-height: 1.5;
            color: #bbb;
        }}
        .empty-msg {{
            color: #666;
            font-size: 14px;
            text-align: center;
            padding: 40px 16px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>XResearch</h1>
        <div class="updated">Updated: {escape(updated)}</div>
    </div>
    <div class="main">
        <div class="section">
            <h2 class="section-title">Paper Digest</h2>
            {paper_html}
        </div>
        <div class="section">
            <h2 class="section-title">Trend Posts</h2>
            {post_html}
        </div>
    </div>
</body>
</html>"""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "index.html").write_text(html, encoding="utf-8")
    logger.info("Generated %s/index.html (%d papers, %d posts)", output_dir, len(papers), len(posts))

    feed = {
        "updated": now.isoformat(),
        "papers": papers,
        "posts": posts,
    }
    (out / "feed.json").write_text(
        json.dumps(feed, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Generated %s/feed.json", output_dir)
