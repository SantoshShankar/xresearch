"""Fetch trends, rank top 3 per category, generate 5 posts. No posting."""

import asyncio
import logging

from src.core.models import TopicDomain, PostType
from src.trends.aggregator import TrendAggregator
from src.trends.ranker import rank_trends
from src.content.generator import PostGenerator

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


async def main():
    # 1. Fetch all trends
    print("Fetching trends from all sources...")
    aggregator = TrendAggregator()
    all_trends = await aggregator.get_trends(
        domains=[TopicDomain.AI, TopicDomain.CRICKET],
        limit=50,
    )
    print(f"Fetched {len(all_trends)} total trends\n")

    # 2. Rank top 3 per category
    top_ai = rank_trends(all_trends, TopicDomain.AI, top_k=3)
    top_cricket = rank_trends(all_trends, TopicDomain.CRICKET, top_k=3)

    print("=" * 70)
    print("TOP 3 AI TRENDS (cosine similarity + majority vote)")
    print("=" * 70)
    for i, t in enumerate(top_ai, 1):
        cluster_size = t.metadata.get("cluster_size", 1)
        sources = t.metadata.get("sources_in_cluster", [t.source.value])
        print(f"  {i}. {t.title[:75]}")
        print(f"     Sources: {', '.join(sources)} | Cluster size: {cluster_size} | Score: {t.raw_score:.0f}")
        if t.description:
            print(f"     {t.description[:100]}")
        print()

    print("=" * 70)
    print("TOP 3 CRICKET TRENDS (cosine similarity + majority vote)")
    print("=" * 70)
    for i, t in enumerate(top_cricket, 1):
        cluster_size = t.metadata.get("cluster_size", 1)
        sources = t.metadata.get("sources_in_cluster", [t.source.value])
        print(f"  {i}. {t.title[:75]}")
        print(f"     Sources: {', '.join(sources)} | Cluster size: {cluster_size} | Score: {t.raw_score:.0f}")
        if t.description:
            print(f"     {t.description[:100]}")
        print()

    # 3. Generate posts — pick from top trends
    selected = top_ai + top_cricket
    if not selected:
        print("No trends to generate posts from!")
        return

    print("=" * 70)
    print(f"GENERATING 5 POSTS from {len(selected)} selected trends...")
    print("=" * 70)

    generator = PostGenerator()

    # Generate 1 post per trend (up to 5)
    posts = await generator.generate_posts(
        trends=selected[:5],
        count=1,
        post_type=PostType.SINGLE,
    )

    print(f"\nGenerated {len(posts)} posts:\n")
    for i, post in enumerate(posts, 1):
        domain = post.trend.domain.value.upper()
        source = post.trend.source.value
        print(f"--- Post {i} [{domain}] (from: {source}) ---")
        print(f"Trend: {post.trend.title[:60]}")
        print()
        print(f"  {post.content}")
        print(f"  {' '.join(post.hashtags)}")
        print(f"  Length: {len(post.content)} chars | Valid: {post.is_valid_length}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
