from __future__ import annotations

import logging

import httpx

from src.core import config
from src.core.models import Trend, TrendSource, TopicDomain
from src.trends.base import BaseTrendSource

logger = logging.getLogger(__name__)

GNEWS_SEARCH_URL = "https://gnews.io/api/v4/search"

DOMAIN_QUERIES: dict[TopicDomain, str] = {
    TopicDomain.AI: "artificial intelligence OR LLM OR machine learning",
    TopicDomain.CRICKET: "cricket OR IPL OR T20",
}


class GNewsTrendsFetcher(BaseTrendSource):
    """Fetch trending news via GNews. Requires GNEWS_API_KEY."""

    name = "gnews"

    def __init__(self, lang: str = "en", country: str = "us"):
        self.lang = lang
        self.country = country
        self.api_key = config.GNEWS_API_KEY

    async def fetch(self, domains: list[TopicDomain] | None = None, limit: int = 10) -> list[Trend]:
        if not self.api_key:
            logger.warning("GNEWS_API_KEY not set, skipping GNews")
            return []

        target_domains = domains or [TopicDomain.AI, TopicDomain.CRICKET]
        trends: list[Trend] = []

        for domain in target_domains:
            query = DOMAIN_QUERIES.get(domain)
            if not query:
                continue

            params = {
                "q": query,
                "lang": self.lang,
                "country": self.country,
                "max": min(limit, 10),
                "apikey": self.api_key,
            }

            try:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(GNEWS_SEARCH_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
            except httpx.HTTPError as e:
                logger.error("GNews fetch failed for %s: %s", domain, e)
                continue

            articles = data.get("articles", [])
            for article in articles:
                trends.append(Trend(
                    title=article.get("title", ""),
                    description=article.get("description", ""),
                    url=article.get("url", ""),
                    source=TrendSource.GNEWS,
                    domain=domain,
                    metadata={
                        "published_at": article.get("publishedAt", ""),
                        "source_name": article.get("source", {}).get("name", ""),
                    },
                ))

            if len(trends) >= limit:
                break

        return trends[:limit]
