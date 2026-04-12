from __future__ import annotations

import logging

import feedparser
import httpx

from src.core.models import Trend, TrendSource, TopicDomain
from src.trends.base import BaseTrendSource

logger = logging.getLogger(__name__)

# Curated RSS feeds by domain
DEFAULT_FEEDS: dict[TopicDomain, list[str]] = {
    TopicDomain.AI: [
        "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US",
        "https://www.technologyreview.com/feed/",
        "https://blog.google/technology/ai/rss/",
    ],
    TopicDomain.CRICKET: [
        "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
        "https://news.google.com/rss/search?q=cricket+IPL&hl=en-US",
    ],
}


class RSSTrendsFetcher(BaseTrendSource):
    """Fetch trends from curated RSS feeds — free, reliable, no auth."""

    name = "rss"

    def __init__(self, feeds: dict[TopicDomain, list[str]] | None = None):
        self.feeds = feeds or DEFAULT_FEEDS

    async def fetch(self, domains: list[TopicDomain] | None = None, limit: int = 10) -> list[Trend]:
        target_domains = domains or list(self.feeds.keys())
        trends: list[Trend] = []

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for domain in target_domains:
                feed_urls = self.feeds.get(domain, [])
                for url in feed_urls:
                    entries = await self._fetch_feed(client, url, domain)
                    trends.extend(entries)

        # Deduplicate by title
        seen: set[str] = set()
        unique: list[Trend] = []
        for t in trends:
            key = t.title.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(t)

        return unique[:limit]

    async def _fetch_feed(self, client: httpx.AsyncClient, url: str, domain: TopicDomain) -> list[Trend]:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("RSS fetch failed for %s: %s", url, e)
            return []

        feed = feedparser.parse(resp.text)
        trends: list[Trend] = []

        for entry in feed.entries[:10]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "")[:300]

            trends.append(Trend(
                title=title,
                description=summary,
                url=link,
                source=TrendSource.RSS,
                domain=domain,
                metadata={
                    "feed_url": url,
                    "published": entry.get("published", ""),
                },
            ))

        return trends
