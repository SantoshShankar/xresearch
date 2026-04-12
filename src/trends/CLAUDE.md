# Team: Trends

## Responsibility
Fetch, aggregate, and rank trending topics from multiple sources across X, web, news, and domain-specific feeds (AI/LLMs, cricket).

## Scope
- X/Twitter trend fetching (hashtags, trending topics, viral tweets)
- Google Trends integration
- News API aggregation (NewsAPI, GNews, RSS)
- Reddit trend monitoring (r/MachineLearning, r/LocalLLaMA, r/Cricket, r/artificial)
- AI-specific sources (Hugging Face trending, arXiv, Papers With Code, Hacker News)
- Cricket-specific sources (ESPNcricinfo, live scores, match events)
- Trend scoring and deduplication across sources

## Interface
- Expose a unified `get_trends(topics: list[str]) -> list[Trend]` interface
- Each source implements a `TrendSource` base class
- Output `Trend` objects defined in `src/core/models.py`

## Conventions
- Each source gets its own module (e.g., `x_trends.py`, `google_trends.py`, `reddit_trends.py`)
- All HTTP calls use `httpx` with async support
- Cache results to avoid redundant API calls (respect rate limits)
- Log all API failures with source name and error
