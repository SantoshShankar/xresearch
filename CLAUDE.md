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
│   ├── arxiv_deep.py  # Deep arXiv fetcher with Claude-as-judge ranking
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

tests/              # Test scripts
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

## Paper Ranking

Papers are scored on a 0-16 scale:
- **Claude judge** (0-10): rates novelty and impact from abstract
- **Lab boost** (+3): papers from OpenAI, Anthropic, Meta, Google, Apple, DeepSeek, Microsoft
- **Keyword boost** (+2): breakthrough language ("state-of-the-art", "novel", "outperforms")
- **Agentic boost** (+1): papers about agentic AI

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

## TODO

- Cron setup: trend posts every 6 hours, paper digest daily
- RLHF-style feedback loop for paper ranking (user rates papers → improves future ranking)
- Reddit integration (needs credentials)
