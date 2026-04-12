from __future__ import annotations

import logging

from huggingface_hub import HfApi

from src.core.models import Trend, TrendSource, TopicDomain
from src.trends.base import BaseTrendSource

logger = logging.getLogger(__name__)


class HuggingFaceTrendsFetcher(BaseTrendSource):
    """Fetch trending models and spaces from Hugging Face — free, no auth needed."""

    name = "huggingface"

    async def fetch(self, domains: list[TopicDomain] | None = None, limit: int = 10) -> list[Trend]:
        trends: list[Trend] = []
        api = HfApi()

        try:
            models = list(api.list_models(sort="last_modified", limit=limit))
        except Exception as e:
            logger.error("HuggingFace models fetch failed: %s", e)
            models = []

        for model in models:
            title = f"Trending model: {model.id}"
            tags = model.tags or []
            description = f"Tags: {', '.join(tags[:10])}" if tags else ""

            trends.append(Trend(
                title=title,
                description=description,
                url=f"https://huggingface.co/{model.id}",
                source=TrendSource.HUGGINGFACE,
                domain=TopicDomain.AI,
                raw_score=float(model.likes or 0),
                metadata={
                    "model_id": model.id,
                    "downloads": model.downloads,
                    "likes": model.likes,
                    "tags": tags[:10],
                },
            ))

        try:
            spaces = list(api.list_spaces(sort="last_modified", limit=limit))
        except Exception as e:
            logger.error("HuggingFace spaces fetch failed: %s", e)
            spaces = []

        for space in spaces:
            title = f"Trending space: {space.id}"
            trends.append(Trend(
                title=title,
                url=f"https://huggingface.co/spaces/{space.id}",
                source=TrendSource.HUGGINGFACE,
                domain=TopicDomain.AI,
                raw_score=float(space.likes or 0),
                metadata={
                    "space_id": space.id,
                    "likes": space.likes,
                },
            ))

        trends.sort(key=lambda t: t.raw_score, reverse=True)
        return trends[:limit]
