from __future__ import annotations

import logging

import praw

from src.core import config
from src.core.models import Trend, TrendSource, TopicDomain
from src.trends.base import BaseTrendSource

logger = logging.getLogger(__name__)

# Subreddits by domain
SUBREDDIT_MAP: dict[TopicDomain, list[str]] = {
    TopicDomain.AI: ["MachineLearning", "LocalLLaMA", "artificial", "ChatGPT", "ClaudeAI"],
    TopicDomain.LLM: ["LocalLLaMA", "ChatGPT", "ClaudeAI"],
    TopicDomain.CRICKET: ["Cricket", "CricketShitpost", "IPL"],
    TopicDomain.GENERAL: ["technology", "programming"],
}


class RedditTrendsFetcher(BaseTrendSource):
    name = "reddit"

    def __init__(self):
        self._reddit: praw.Reddit | None = None

    def _get_client(self) -> praw.Reddit:
        if self._reddit is None:
            self._reddit = praw.Reddit(
                client_id=config.REDDIT_CLIENT_ID,
                client_secret=config.REDDIT_CLIENT_SECRET,
                user_agent=config.REDDIT_USER_AGENT,
            )
        return self._reddit

    async def fetch(self, domains: list[TopicDomain] | None = None, limit: int = 10) -> list[Trend]:
        """Fetch hot posts from relevant subreddits. Note: PRAW is sync, wrapped for interface consistency."""
        target_domains = domains or [TopicDomain.AI, TopicDomain.CRICKET]
        subreddits: set[str] = set()
        for d in target_domains:
            subreddits.update(SUBREDDIT_MAP.get(d, []))

        if not subreddits:
            return []

        trends: list[Trend] = []
        reddit = self._get_client()
        combined = "+".join(subreddits)

        try:
            subreddit = reddit.subreddit(combined)
            for post in subreddit.hot(limit=limit * 2):
                if post.stickied:
                    continue

                text = f"{post.title} {post.selftext[:200]}"
                domain = self._classify_domain(text)
                if domains and domain not in domains:
                    continue

                trends.append(Trend(
                    title=post.title,
                    description=post.selftext[:300] if post.selftext else "",
                    url=f"https://reddit.com{post.permalink}",
                    source=TrendSource.REDDIT,
                    domain=domain,
                    raw_score=float(post.score),
                    metadata={
                        "subreddit": post.subreddit.display_name,
                        "num_comments": post.num_comments,
                        "upvote_ratio": post.upvote_ratio,
                    },
                ))

                if len(trends) >= limit:
                    break
        except Exception as e:
            logger.error("Reddit fetch failed: %s", e)

        return trends
