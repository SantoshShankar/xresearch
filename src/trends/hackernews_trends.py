from __future__ import annotations

import asyncio
import logging

import httpx

from src.core.models import Trend, TrendSource, TopicDomain
from src.trends.base import BaseTrendSource

logger = logging.getLogger(__name__)

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"


class HackerNewsTrendsFetcher(BaseTrendSource):
    """Fetch top Hacker News stories — free, no auth, no rate limits."""

    name = "hacker_news"

    async def fetch(self, domains: list[TopicDomain] | None = None, limit: int = 10) -> list[Trend]:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(HN_TOP_URL)
                resp.raise_for_status()
                story_ids = resp.json()
        except httpx.HTTPError as e:
            logger.error("HN top stories fetch failed: %s", e)
            return []

        # Fetch top N story details concurrently
        fetch_count = min(len(story_ids), limit * 3)  # fetch extra for filtering
        stories = await self._fetch_stories(story_ids[:fetch_count])

        trends: list[Trend] = []
        for story in stories:
            title = story.get("title", "")
            domain = self._classify_domain(title)

            if domains and domain not in domains:
                continue

            trends.append(Trend(
                title=title,
                url=story.get("url", f"https://news.ycombinator.com/item?id={story.get('id')}"),
                source=TrendSource.HACKER_NEWS,
                domain=domain,
                raw_score=float(story.get("score", 0)),
                metadata={
                    "hn_id": story.get("id"),
                    "num_comments": story.get("descendants", 0),
                    "by": story.get("by", ""),
                },
            ))

            if len(trends) >= limit:
                break

        return trends

    async def _fetch_stories(self, ids: list[int]) -> list[dict]:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            tasks = [self._fetch_item(client, sid) for sid in ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]

    @staticmethod
    async def _fetch_item(client: httpx.AsyncClient, story_id: int) -> dict:
        resp = await client.get(HN_ITEM_URL.format(id=story_id))
        resp.raise_for_status()
        return resp.json()
