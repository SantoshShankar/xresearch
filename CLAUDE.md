# XResearch

## Overview

Research tool that monitors trending topics on X (Twitter) and the web around **AI, LLMs, and cricket**, then generates X posts and paper summaries. Delivers via iMessage and displays on a web dashboard.

## Tech Stack

- **Language:** Python 3.11+
- **LLM:** Claude API (anthropic SDK) for post generation, paper summarization, and paper ranking
- **Web:** FastAPI + inline HTML/CSS (dark theme dashboard)
- **DB:** SQLite (WAL mode) at `db/xresearch.db`
- **Delivery:** iMessage via macOS AppleScript

## Project Structure

```
src/
├── core/           # Shared models, config, DB
│   ├── models.py   # Trend, Post, PostResult, PostMetrics (Pydantic)
│   ├── config.py   # Env-based config (.env via python-dotenv)
│   └── db.py       # SQLite storage for posts + paper summaries
├── trends/         # Trend fetching & aggregation
│   ├── base.py     # BaseTrendSource ABC + domain classifier
│   ├── aggregator.py  # Concurrent fetch, dedup, balanced round-robin ranking
│   ├── ranker.py   # Cosine similarity clustering + majority vote + recency boost
│   ├── arxiv_deep.py  # Multi-source paper fetcher (arXiv + HuggingFace daily) + Claude-as-judge ranking
│   ├── google_trends.py, reddit_trends.py, news_trends.py
│   ├── hackernews_trends.py, huggingface_trends.py
│   ├── cricket_trends.py, rss_trends.py
│   └── (each source implements BaseTrendSource)
├── content/        # LLM-powered generation
│   ├── generator.py       # Post generation via Claude API
│   ├── paper_summarizer.py # arXiv paper summarization
│   └── prompts/           # Prompt templates (single_post, thread, hashtags)
└── publisher/      # Delivery
    ├── x_publisher.py  # X API posting via Tweepy (dev mode supported)
    └── imessage.py     # iMessage delivery via AppleScript

tests/              # Test scripts + eval harness (eval_paper_ranking.py)
plans/              # Improvement plans
web.py              # FastAPI dashboard (localhost:8080)
run_and_notify.py   # Trend posts pipeline: fetch → rank → generate → save → iMessage
run_papers.py       # Paper pipeline: fetch → rank (Claude judge) → summarize → save → iMessage
main.py             # Basic trend scan entry point
```

## Teams

Each team has its own `CLAUDE.md` with scope, interfaces, and conventions.

| Team | Directory | Responsibility |
|------|-----------|---------------|
| **Core** | `src/core/` | Pydantic models, config, SQLite DB |
| **Trends** | `src/trends/` | 8 source fetchers + aggregator + ranker |
| **Content** | `src/content/` | Claude-powered post generation + paper summarization |
| **Publisher** | `src/publisher/` | X API posting + iMessage delivery |

## Trend Sources (8 total)

| Source | Library | Auth | Status |
|--------|---------|------|--------|
| Google Trends RSS | httpx | None | Working |
| Hacker News | httpx | None | Working |
| arXiv | arxiv | None | Working |
| HuggingFace | huggingface_hub | None | Working |
| RSS Feeds | feedparser | None | Working |
| CricAPI | httpx | API key | Working |
| GNews | httpx | API key | Working (rate limited) |
| Reddit | praw | Client ID/secret | Needs credentials |

## Paper Retrieval

Papers are fetched from multiple sources and deduped by arxiv ID:
- **HuggingFace daily papers** (`huggingface.co/api/daily_papers`): curated social-signal source with upvotes — dominant retrieval signal
- **arXiv broad scan** (`fetch_recent_arxiv`): category-based sweep across cs.AI/CL/LG/MA for configurable time window
- **arXiv agentic queries** (`fetch_agentic_papers`): targeted abstract keyword search for agent-related papers

## Paper Ranking

Papers are scored on a 0-18 scale:
- **Claude judge** (0-10): few-shot rubric scoring 4 dimensions (novelty, rigor, practical_impact, agent_relevance) — returns structured JSON, mean of 4 scores
- **Social signal boost** (0-5): +4 for HuggingFace daily papers, +1 per additional curated source (capped at 5)
- **Lab boost** (0-2): papers authored by top labs (matched against authors string only, word-boundary — no title/abstract false positives)
- **Agentic boost** (+1): papers retrieved via agentic AI queries

## Running

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in API keys

# Trend posts → iMessage
PYTHONPATH=. python run_and_notify.py

# Paper summaries → iMessage
PYTHONPATH=. python run_papers.py

# Web dashboard
PYTHONPATH=. uvicorn web:app --port 8080

# Basic trend scan (stdout only)
PYTHONPATH=. python main.py
```

## Required Environment Variables

- `ANTHROPIC_API_KEY` — required for post generation and paper ranking
- `IMESSAGE_RECIPIENT` — phone number or Apple ID for iMessage delivery
- `CRICAPI_KEY` — for live cricket scores (free: 100 req/day)
- `GNEWS_API_KEY` — for news trends
- `NEWSAPI_KEY` — optional, for NewsAPI.org

## Conventions

- Python 3.11+, PEP 8, type hints
- All HTTP calls use `httpx` with `follow_redirects=True`
- Secrets in `.env` (never commit `.env`)
- All trend sources implement `BaseTrendSource` ABC
- DB saves happen before iMessage delivery (so dashboard always has data)
- Dev mode (`DEV_MODE=true`) prevents actual X posting

## Eval Harness

`tests/eval_paper_ranking.py` measures retrieval and ranking quality against a validation set of known-good papers (grounded by arxiv ID, not keywords). Supports `--quick` (skip Claude judge), `--baseline` (old pipeline), and `--week` flags. See `plans/paper_ranking_improvement.md` for the full improvement plan.

## TODO

- Cron setup: trend posts every 6 hours, paper digest daily
- RLHF-style feedback loop for paper ranking (user rates papers → improves future ranking)
- Reddit integration (needs credentials)
- Add more retrieval sources: alphaXiv trending, Papers With Code, HN arxiv links
