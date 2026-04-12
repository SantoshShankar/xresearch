from __future__ import annotations

import logging
from datetime import datetime

import tweepy

from src.core import config
from src.core.models import Post, PostResult, PostStatus, PostMetrics

logger = logging.getLogger(__name__)


class XPublisher:
    """Publish posts to X via API v2 using Tweepy."""

    def __init__(self):
        self._client: tweepy.Client | None = None

    def _get_client(self) -> tweepy.Client:
        if self._client is None:
            self._client = tweepy.Client(
                bearer_token=config.X_BEARER_TOKEN,
                consumer_key=config.X_API_KEY,
                consumer_secret=config.X_API_SECRET,
                access_token=config.X_ACCESS_TOKEN,
                access_token_secret=config.X_ACCESS_TOKEN_SECRET,
            )
        return self._client

    def publish(self, post: Post) -> PostResult:
        """Publish a single post or thread to X."""
        if config.DEV_MODE:
            logger.info("[DEV MODE] Would post: %s", self._format_post(post))
            return PostResult(
                post=post,
                status=PostStatus.DRAFT,
                post_id="dev-mode",
            )

        try:
            client = self._get_client()

            if post.post_type.value == "thread" and post.thread_parts:
                return self._publish_thread(client, post)

            text = self._format_post(post)
            response = client.create_tweet(text=text)
            tweet_id = str(response.data["id"])

            logger.info("Published tweet %s", tweet_id)
            return PostResult(
                post=post,
                status=PostStatus.POSTED,
                post_id=tweet_id,
                posted_at=datetime.utcnow(),
            )
        except tweepy.TweepyException as e:
            logger.error("Publish failed: %s", e)
            return PostResult(
                post=post,
                status=PostStatus.FAILED,
                error=str(e),
            )

    def _publish_thread(self, client: tweepy.Client, post: Post) -> PostResult:
        """Publish a thread by replying to each previous tweet."""
        hashtag_str = " ".join(post.hashtags)
        previous_id: str | None = None
        first_id: str = ""

        for i, part in enumerate(post.thread_parts):
            text = part
            # Add hashtags to last tweet
            if i == len(post.thread_parts) - 1 and hashtag_str:
                text = f"{text}\n\n{hashtag_str}"

            try:
                response = client.create_tweet(
                    text=text,
                    in_reply_to_tweet_id=previous_id,
                )
                tweet_id = str(response.data["id"])
                if i == 0:
                    first_id = tweet_id
                previous_id = tweet_id
            except tweepy.TweepyException as e:
                logger.error("Thread publish failed at part %d: %s", i, e)
                return PostResult(
                    post=post,
                    status=PostStatus.FAILED,
                    post_id=first_id,
                    error=f"Thread failed at part {i}: {e}",
                )

        logger.info("Published thread starting at %s", first_id)
        return PostResult(
            post=post,
            status=PostStatus.POSTED,
            post_id=first_id,
            posted_at=datetime.utcnow(),
        )

    def get_metrics(self, post_id: str) -> PostMetrics:
        """Fetch metrics for a posted tweet."""
        client = self._get_client()
        try:
            tweet = client.get_tweet(
                post_id,
                tweet_fields=["public_metrics"],
            )
            metrics = tweet.data.get("public_metrics", {}) if tweet.data else {}
            return PostMetrics(
                post_id=post_id,
                likes=metrics.get("like_count", 0),
                retweets=metrics.get("retweet_count", 0),
                replies=metrics.get("reply_count", 0),
                impressions=metrics.get("impression_count", 0),
            )
        except tweepy.TweepyException as e:
            logger.error("Metrics fetch failed for %s: %s", post_id, e)
            return PostMetrics(post_id=post_id)

    @staticmethod
    def _format_post(post: Post) -> str:
        """Format post content with hashtags."""
        hashtag_str = " ".join(post.hashtags)
        if hashtag_str:
            return f"{post.content}\n\n{hashtag_str}"
        return post.content
