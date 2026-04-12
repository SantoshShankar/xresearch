"""XResearch — Trend-aware X post generator."""

import asyncio
import logging

from src.core.models import TopicDomain, PostType
from src.trends.aggregator import TrendAggregator
from src.content.generator import PostGenerator
from src.publisher.x_publisher import XPublisher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("xresearch")


async def main():
    # 1. Fetch trends
    logger.info("Scanning for trends...")
    aggregator = TrendAggregator()
    trends = await aggregator.get_trends(
        domains=[TopicDomain.AI, TopicDomain.CRICKET],
        limit=10,
    )
    logger.info("Found %d trends", len(trends))

    if not trends:
        logger.warning("No trends found. Check API keys and network.")
        return

    # Show discovered trends
    print("\n" + "=" * 60)
    print("DISCOVERED TRENDS")
    print("=" * 60)
    for i, trend in enumerate(trends, 1):
        print(f"  {i}. [{trend.source.value}] [{trend.domain.value}] {trend.title}")

    # 2. Generate posts
    logger.info("Generating posts...")
    generator = PostGenerator()
    posts = await generator.generate_posts(
        trends=trends[:5],  # top 5 trends
        count=1,
        post_type=PostType.SINGLE,
    )
    logger.info("Generated %d posts", len(posts))

    # Show generated posts
    print("\n" + "=" * 60)
    print("GENERATED POSTS")
    print("=" * 60)
    for i, post in enumerate(posts, 1):
        print(f"\n--- Post {i} (trend: {post.trend.title[:50]}...) ---")
        print(f"  {post.content}")
        print(f"  Hashtags: {' '.join(post.hashtags)}")
        print(f"  Length: {len(post.content)} chars | Valid: {post.is_valid_length}")

    # 3. Publish (dev mode by default — just logs, no actual posting)
    publisher = XPublisher()
    print("\n" + "=" * 60)
    print("PUBLISHING (DEV_MODE — dry run)")
    print("=" * 60)
    for post in posts:
        result = publisher.publish(post)
        print(f"  [{result.status.value}] {post.content[:60]}...")


if __name__ == "__main__":
    asyncio.run(main())
