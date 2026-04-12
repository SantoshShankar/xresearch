"""XResearch Dashboard — view generated posts and paper summaries."""

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from src.core.db import get_posts, get_paper_summaries, get_post_count, get_paper_count

app = FastAPI(title="XResearch Dashboard")


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    tab: str = Query("all", pattern="^(all|ai|cricket|papers)$"),
    page: int = Query(1, ge=1),
):
    per_page = 20
    offset = (page - 1) * per_page

    if tab == "papers":
        papers = get_paper_summaries(limit=per_page, offset=offset)
        total = get_paper_count()
        content = _render_papers(papers)
    else:
        domain = {"ai": "ai", "cricket": "cricket"}.get(tab)
        posts = get_posts(domain=domain, limit=per_page, offset=offset)
        total = get_post_count(domain=domain)
        content = _render_posts(posts)

    total_pages = max(1, (total + per_page - 1) // per_page)
    pagination = _render_pagination(tab, page, total_pages)

    return _page(tab, content, pagination, total)


def _render_posts(posts: list[dict]) -> str:
    if not posts:
        return '<div class="empty">No posts yet. Run <code>python run_and_notify.py</code> to generate some.</div>'

    cards = []
    for p in posts:
        domain = p["domain"].upper()
        domain_class = p["domain"]
        hashtags = p["hashtags"] if p["hashtags"] else ""
        url = p.get("trend_url", "")
        link = f'<a href="{url}" target="_blank" class="link">🔗 Source</a>' if url else ""
        created = p["created_at"][:16].replace("T", " ")

        cards.append(f"""
        <div class="card">
            <div class="card-header">
                <span class="badge {domain_class}">{domain}</span>
                <span class="source">{p.get('source', '')}</span>
                <span class="time">{created}</span>
            </div>
            <div class="card-body">
                <p class="content">{p['content']}</p>
                <div class="hashtags">{hashtags}</div>
            </div>
            <div class="card-footer">
                <span class="trend-title">📌 {p.get('trend_title', '')[:70]}</span>
                {link}
            </div>
        </div>
        """)
    return "\n".join(cards)


def _render_papers(papers: list[dict]) -> str:
    if not papers:
        return '<div class="empty">No papers yet. Run <code>python run_papers.py</code> to generate some.</div>'

    cards = []
    for p in papers:
        tag = "AGENTIC" if p["is_agentic"] else "TRENDING"
        tag_class = "ai" if p["is_agentic"] else "general"
        score = p.get("interest_score", 0)
        url = p.get("paper_url", "")
        pdf = p.get("pdf_url", "")
        link = f'<a href="{url}" target="_blank" class="link">📄 Paper</a>' if url else ""
        pdf_link = f'<a href="{pdf}" target="_blank" class="link">📥 PDF</a>' if pdf else ""
        created = p["created_at"][:16].replace("T", " ")
        authors = p.get("authors", "")

        cards.append(f"""
        <div class="card paper">
            <div class="card-header">
                <span class="badge {tag_class}">{tag}</span>
                <span class="score">⭐ {score:.1f}/16</span>
                <span class="time">{created}</span>
            </div>
            <div class="card-body">
                <h3 class="paper-title">{p['title']}</h3>
                <p class="authors">👥 {authors}</p>
                <p class="content">{p['summary']}</p>
            </div>
            <div class="card-footer">
                {link} {pdf_link}
            </div>
        </div>
        """)
    return "\n".join(cards)


def _render_pagination(tab: str, current: int, total: int) -> str:
    if total <= 1:
        return ""
    links = []
    if current > 1:
        links.append(f'<a href="/?tab={tab}&page={current-1}" class="page-link">← Prev</a>')
    links.append(f'<span class="page-info">Page {current} of {total}</span>')
    if current < total:
        links.append(f'<a href="/?tab={tab}&page={current+1}" class="page-link">Next →</a>')
    return f'<div class="pagination">{"".join(links)}</div>'


def _page(tab: str, content: str, pagination: str, total: int) -> str:
    def active(t: str) -> str:
        return "active" if tab == t else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>XResearch Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            min-height: 100vh;
        }}
        .header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 24px 32px;
            border-bottom: 1px solid #2a2a4a;
        }}
        .header h1 {{
            font-size: 24px;
            font-weight: 700;
            color: #fff;
            margin-bottom: 4px;
        }}
        .header .subtitle {{
            color: #888;
            font-size: 14px;
        }}
        .tabs {{
            display: flex;
            gap: 0;
            background: #111;
            border-bottom: 1px solid #222;
            padding: 0 32px;
        }}
        .tab {{
            padding: 14px 24px;
            color: #888;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }}
        .tab:hover {{ color: #ccc; }}
        .tab.active {{
            color: #60a5fa;
            border-bottom-color: #60a5fa;
        }}
        .count {{
            background: #222;
            color: #888;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
            margin-left: 6px;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            padding: 24px 16px;
        }}
        .card {{
            background: #151515;
            border: 1px solid #252525;
            border-radius: 12px;
            margin-bottom: 16px;
            overflow: hidden;
            transition: border-color 0.2s;
        }}
        .card:hover {{ border-color: #404040; }}
        .card-header {{
            padding: 14px 18px 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .badge {{
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .badge.ai {{ background: #1e3a5f; color: #60a5fa; }}
        .badge.cricket {{ background: #2d4a1e; color: #86efac; }}
        .badge.general {{ background: #4a3a1e; color: #fbbf24; }}
        .source {{
            color: #666;
            font-size: 12px;
        }}
        .score {{
            color: #fbbf24;
            font-size: 13px;
            font-weight: 600;
        }}
        .time {{
            color: #555;
            font-size: 12px;
            margin-left: auto;
        }}
        .card-body {{
            padding: 12px 18px;
        }}
        .content {{
            font-size: 15px;
            line-height: 1.6;
            color: #d0d0d0;
        }}
        .paper-title {{
            font-size: 16px;
            font-weight: 600;
            color: #e8e8e8;
            margin-bottom: 6px;
            line-height: 1.4;
        }}
        .authors {{
            color: #888;
            font-size: 13px;
            margin-bottom: 10px;
        }}
        .hashtags {{
            color: #60a5fa;
            font-size: 13px;
            margin-top: 8px;
        }}
        .card-footer {{
            padding: 10px 18px 14px;
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .trend-title {{
            color: #666;
            font-size: 12px;
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .link {{
            color: #60a5fa;
            text-decoration: none;
            font-size: 13px;
            white-space: nowrap;
        }}
        .link:hover {{ text-decoration: underline; }}
        .pagination {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 16px;
            padding: 20px 0;
        }}
        .page-link {{
            color: #60a5fa;
            text-decoration: none;
            font-size: 14px;
        }}
        .page-info {{ color: #666; font-size: 14px; }}
        .empty {{
            text-align: center;
            color: #666;
            padding: 60px 20px;
            font-size: 15px;
        }}
        .empty code {{
            background: #222;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>XResearch</h1>
        <div class="subtitle">AI &amp; Cricket Trend Posts + Paper Summaries</div>
    </div>
    <div class="tabs">
        <a href="/?tab=all" class="tab {active('all')}">All Posts</a>
        <a href="/?tab=ai" class="tab {active('ai')}">AI</a>
        <a href="/?tab=cricket" class="tab {active('cricket')}">Cricket</a>
        <a href="/?tab=papers" class="tab {active('papers')}">Papers</a>
    </div>
    <div class="container">
        {content}
        {pagination}
    </div>
</body>
</html>"""
