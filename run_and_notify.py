"""Fetch trends, generate posts, send digest via iMessage. Designed for cron."""

import asyncio
import logging
import os
import sys

from src.core.models import TopicDomain, PostType
from src.core.db import save_post
from src.trends.aggregator import TrendAggregator
from src.trends.ranker import rank_trends
from src.content.generator import PostGenerator
from src.publisher.imessage import send_posts_via_imessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("xresearch")

IMESSAGE_RECIPIENT = os.getenv("IMESSAGE_RECIPIENT", "")


async def run():
    # 1. Fetch trends
    logger.info("Fetching trends...")
    aggregator = TrendAggregator()
    all_trends = await aggregator.get_trends(
        domains=[TopicDomain.AI, TopicDomain.CRICKET],
        limit=50,
    )
    logger.info("Fetched %d trends", len(all_trends))

    if not all_trends:
        logger.warning("No trends found, skipping")
        return

    # 2. Rank top 3 per category
    top_ai = rank_trends(all_trends, TopicDomain.AI, top_k=3)
    top_cricket = rank_trends(all_trends, TopicDomain.CRICKET, top_k=3)
    selected = top_ai + top_cricket

    if not selected:
        logger.warning("No ranked trends, skipping")
        return

    logger.info("Selected %d trends (AI: %d, Cricket: %d)", len(selected), len(top_ai), len(top_cricket))

    # 3. Generate posts
    logger.info("Generating posts...")
    generator = PostGenerator()
    posts = await generator.generate_posts(
        trends=selected[:5],
        count=1,
        post_type=PostType.SINGLE,
    )
    logger.info("Generated %d posts", len(posts))

    # 4. Save to DB + send via iMessage
    post_dicts = []
    for p in posts:
        save_post(
            content=p.content,
            hashtags=p.hashtags,
            domain=p.trend.domain.value,
            source=p.trend.source.value,
            trend_title=p.trend.title,
            trend_url=p.trend.url,
            post_type="trend",
            score=p.trend.score,
        )
        post_dicts.append({
            "content": p.content,
            "hashtags": p.hashtags,
            "domain": p.trend.domain.value,
            "trend_title": p.trend.title,
            "url": p.trend.url,
        })
    logger.info("Saved %d posts to DB", len(post_dicts))

    recipient = IMESSAGE_RECIPIENT
    if not recipient:
        logger.warning("IMESSAGE_RECIPIENT not set — printing to stdout")
        for i, post in enumerate(posts, 1):
            print(f"\n--- Post {i} [{post.trend.domain.value.upper()}] ---")
            print(f"{post.content}")
            print(f"{' '.join(post.hashtags)}")
        return

    sent = send_posts_via_imessage(recipient, post_dicts)
    if sent:
        logger.info("Digest sent to %s", recipient)
    else:
        logger.error("Failed to send digest")


if __name__ == "__main__":
    asyncio.run(run())
