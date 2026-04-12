from __future__ import annotations

import asyncio
import logging

from src.core.models import Trend, TopicDomain
from src.trends.base import BaseTrendSource
from src.trends.google_trends import GoogleTrendsFetcher
from src.trends.reddit_trends import RedditTrendsFetcher
from src.trends.news_trends import GNewsTrendsFetcher
from src.trends.hackernews_trends import HackerNewsTrendsFetcher
from src.trends.huggingface_trends import HuggingFaceTrendsFetcher
from src.trends.arxiv_trends import ArxivTrendsFetcher
from src.trends.cricket_trends import CricketTrendsFetcher
from src.trends.rss_trends import RSSTrendsFetcher

logger = logging.getLogger(__name__)


class TrendAggregator:
    """Fetches from all sources, deduplicates, and ranks trends."""

    def __init__(self, sources: list[BaseTrendSource] | None = None):
        self.sources = sources or self._default_sources()

    @staticmethod
    def _default_sources() -> list[BaseTrendSource]:
        return [
            GoogleTrendsFetcher(),
            RedditTrendsFetcher(),
            GNewsTrendsFetcher(),
            HackerNewsTrendsFetcher(),
            HuggingFaceTrendsFetcher(),
            ArxivTrendsFetcher(),
            CricketTrendsFetcher(),
            RSSTrendsFetcher(),
        ]

    async def get_trends(
        self,
        domains: list[TopicDomain] | None = None,
        limit: int = 20,
    ) -> list[Trend]:
        """Fetch trends from all sources concurrently, deduplicate, and rank."""
        tasks = [source.fetch(domains=domains, limit=limit) for source in self.sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_trends: list[Trend] = []
        for i, result in enumerate(results):
            source_name = self.sources[i].name
            if isinstance(result, Exception):
                logger.error("Source %s failed: %s", source_name, result)
                continue
            logger.info("Source %s returned %d trends", source_name, len(result))
            all_trends.extend(result)

        unique = self._deduplicate(all_trends)
        ranked = self._rank_balanced(unique, limit)
        return ranked

    @staticmethod
    def _deduplicate(trends: list[Trend]) -> list[Trend]:
        seen: set[str] = set()
        unique: list[Trend] = []
        for t in trends:
            key = t.title.lower().strip()[:80]
            if key not in seen:
                seen.add(key)
                unique.append(t)
        return unique

    @staticmethod
    def _rank_balanced(trends: list[Trend], limit: int) -> list[Trend]:
        """Balanced ranking: normalize per-source, then round-robin across sources.

        This ensures no single source (e.g. HuggingFace with huge like counts)
        drowns out other sources.
        """
        # Group by source
        by_source: dict[str, list[Trend]] = {}
        for t in trends:
            by_source.setdefault(t.source.value, []).append(t)

        # Normalize within each source and sort
        for source_trends in by_source.values():
            max_score = max((t.raw_score for t in source_trends), default=1.0) or 1.0
            for t in source_trends:
                t.score = t.raw_score / max_score
            source_trends.sort(key=lambda t: t.score, reverse=True)

        # Round-robin: take top from each source in rotation
        result: list[Trend] = []
        source_iters = {src: iter(items) for src, items in by_source.items()}
        while len(result) < limit and source_iters:
            exhausted = []
            for src, it in source_iters.items():
                if len(result) >= limit:
                    break
                trend = next(it, None)
                if trend is not None:
                    result.append(trend)
                else:
                    exhausted.append(src)
            for src in exhausted:
                del source_iters[src]

        return result
