from __future__ import annotations

import logging
from pathlib import Path

import anthropic

from src.core import config
from src.core.models import Post, PostType, Trend, TopicDomain

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text()


class PostGenerator:
    """Generate X posts from trends using Claude API."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.model = model

    async def generate_posts(
        self,
        trends: list[Trend],
        count: int = 1,
        post_type: PostType = PostType.SINGLE,
    ) -> list[Post]:
        """Generate posts for each trend."""
        posts: list[Post] = []
        for trend in trends:
            for _ in range(count):
                try:
                    if post_type == PostType.SINGLE:
                        post = self._generate_single(trend)
                    else:
                        post = self._generate_thread(trend)
                    posts.append(post)
                except Exception as e:
                    logger.error("Post generation failed for '%s': %s", trend.title, e)
        return posts

    def _generate_single(self, trend: Trend) -> Post:
        prompt = _load_prompt("single_post.txt").format(
            title=trend.title,
            description=trend.description or "No additional details",
            source=trend.source.value,
            domain=trend.domain.value,
        )

        content = self._call_claude(prompt)
        hashtags = self._generate_hashtags(content, trend.domain)

        return Post(
            content=content,
            trend=trend,
            post_type=PostType.SINGLE,
            hashtags=hashtags,
        )

    def _generate_thread(self, trend: Trend) -> Post:
        prompt = _load_prompt("thread_post.txt").format(
            title=trend.title,
            description=trend.description or "No additional details",
            source=trend.source.value,
            domain=trend.domain.value,
        )

        content = self._call_claude(prompt)
        parts = [p.strip() for p in content.split("---") if p.strip()]
        hashtags = self._generate_hashtags(parts[0] if parts else content, trend.domain)

        return Post(
            content=parts[0] if parts else content,
            trend=trend,
            post_type=PostType.THREAD,
            thread_parts=parts,
            hashtags=hashtags,
        )

    def _generate_hashtags(self, post_text: str, domain: TopicDomain) -> list[str]:
        prompt = _load_prompt("hashtags.txt").format(
            domain=domain.value,
            post_text=post_text,
        )

        raw = self._call_claude(prompt)
        tags = [t.strip() for t in raw.split() if t.startswith("#")]
        return tags[:4]

    def _call_claude(self, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
