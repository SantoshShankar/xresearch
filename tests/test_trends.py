"""Test all trend sources and print fetched results."""

import asyncio
import logging
import sys

from src.core.models import TopicDomain
from src.trends.google_trends import GoogleTrendsFetcher
from src.trends.hackernews_trends import HackerNewsTrendsFetcher
from src.trends.huggingface_trends import HuggingFaceTrendsFetcher
from src.trends.arxiv_trends import ArxivTrendsFetcher
from src.trends.news_trends import GNewsTrendsFetcher
from src.trends.cricket_trends import CricketTrendsFetcher
from src.trends.rss_trends import RSSTrendsFetcher
from src.trends.aggregator import TrendAggregator

logging.basicConfig(level=logging.WARNING)


async def test_source(name, fetcher, domains=None, limit=5):
    print(f"\n{'='*70}")
    print(f"SOURCE: {name}")
    print("=" * 70)
    try:
        trends = await fetcher.fetch(domains=domains, limit=limit)
        if not trends:
            print("  (no results)")
            return 0
        for i, t in enumerate(trends, 1):
            print(f"  {i}. [{t.domain.value.upper():8}] {t.title[:80]}")
            if t.description:
                print(f"     {t.description[:100]}")
        print(f"  --- {len(trends)} trends fetched ---")
        return len(trends)
    except Exception as e:
        print(f"  ERROR: {e}")
        return 0


async def test_aggregator():
    print(f"\n{'#'*70}")
    print("AGGREGATOR: All sources combined")
    print("#" * 70)
    aggregator = TrendAggregator()
    trends = await aggregator.get_trends(
        domains=[TopicDomain.AI, TopicDomain.CRICKET],
        limit=20,
    )

    by_source = {}
    for t in trends:
        by_source.setdefault(t.source.value, []).append(t)

    print(f"\nTotal: {len(trends)} trends")
    print("\nBy source:")
    for src, items in sorted(by_source.items()):
        print(f"  {src}: {len(items)}")

    print(f"\n{'='*70}")
    for i, t in enumerate(trends, 1):
        print(f"{i:2}. [{t.source.value:15}] [{t.domain.value.upper():8}] (score:{t.score:.2f})")
        print(f"    {t.title[:80]}")
        if t.description:
            print(f"    {t.description[:120]}")
        print()


async def main():
    domains = [TopicDomain.AI, TopicDomain.CRICKET]
    total = 0

    # Test each source individually
    total += await test_source("Google Trends RSS", GoogleTrendsFetcher(), limit=5)
    total += await test_source("Hacker News", HackerNewsTrendsFetcher(), domains=domains, limit=5)
    total += await test_source("HuggingFace", HuggingFaceTrendsFetcher(), limit=5)
    total += await test_source("arXiv", ArxivTrendsFetcher(), limit=5)
    total += await test_source("GNews", GNewsTrendsFetcher(), domains=domains, limit=5)
    total += await test_source("CricAPI", CricketTrendsFetcher(), limit=5)
    total += await test_source("RSS Feeds", RSSTrendsFetcher(), domains=domains, limit=5)

    print(f"\n{'#'*70}")
    print(f"INDIVIDUAL SOURCES TOTAL: {total} trends")
    print("#" * 70)

    # Test aggregator
    await test_aggregator()


if __name__ == "__main__":
    asyncio.run(main())
