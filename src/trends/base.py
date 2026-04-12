from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from src.core.models import Trend, TopicDomain

logger = logging.getLogger(__name__)


class BaseTrendSource(ABC):
    """Base class for all trend sources."""

    name: str = "base"

    @abstractmethod
    async def fetch(self, domains: list[TopicDomain] | None = None, limit: int = 10) -> list[Trend]:
        """Fetch trending topics, optionally filtered by domain."""
        ...

    def _classify_domain(self, text: str) -> TopicDomain:
        """Simple keyword-based domain classification."""
        text_lower = text.lower()
        ai_keywords = {
            "ai", "artificial intelligence", "machine learning", "ml", "deep learning",
            "neural network", "transformer", "gpt", "llm", "large language model",
            "chatgpt", "claude", "gemini", "openai", "anthropic", "hugging face",
            "diffusion", "generative", "fine-tuning", "rag", "embedding", "agent",
            "multimodal", "reasoning", "benchmark", "open source model",
        }
        cricket_keywords = {
            "cricket", "ipl", "test match", "odi", "t20", "wicket", "batsman",
            "batter", "bowler", "innings", "run chase",
            "world cup cricket", "ashes", "bcci", "icc", "virat", "kohli",
            "sachin", "dhoni", "rohit", "bumrah", "babar", "stokes",
            "super kings", "knight riders", "royal challengers", "mumbai indians",
            "sunrisers", "rajasthan royals", "punjab kings", "delhi capitals",
            "gujarat titans", "lucknow super giants",
        }
        import re
        for kw in ai_keywords:
            if re.search(rf'\b{re.escape(kw)}\b', text_lower):
                return TopicDomain.AI
        for kw in cricket_keywords:
            if re.search(rf'\b{re.escape(kw)}\b', text_lower):
                return TopicDomain.CRICKET
        return TopicDomain.GENERAL
