from __future__ import annotations

import logging

import arxiv

from src.core.models import Trend, TrendSource, TopicDomain
from src.trends.base import BaseTrendSource

logger = logging.getLogger(__name__)

# arXiv categories for AI/LLM research
AI_CATEGORIES = ["cs.AI", "cs.CL", "cs.LG"]


class ArxivTrendsFetcher(BaseTrendSource):
    """Fetch recent popular papers from arXiv — free, no API key."""

    name = "arxiv"

    def __init__(self, categories: list[str] | None = None):
        self.categories = categories or AI_CATEGORIES

    async def fetch(self, domains: list[TopicDomain] | None = None, limit: int = 10) -> list[Trend]:
        cat_query = " OR ".join(f"cat:{c}" for c in self.categories)

        search = arxiv.Search(
            query=cat_query,
            max_results=limit,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        trends: list[Trend] = []
        try:
            client = arxiv.Client()
            for result in client.results(search):
                title = result.title
                summary = result.summary[:300] if result.summary else ""
                categories = [c for c in (result.categories or [])]

                trends.append(Trend(
                    title=title,
                    description=summary,
                    url=result.entry_id,
                    source=TrendSource.ARXIV,
                    domain=TopicDomain.AI,
                    metadata={
                        "authors": [a.name for a in result.authors[:5]],
                        "categories": categories,
                        "published": result.published.isoformat() if result.published else "",
                        "pdf_url": result.pdf_url,
                    },
                ))

                if len(trends) >= limit:
                    break
        except Exception as e:
            logger.error("arXiv fetch failed: %s", e)

        return trends
