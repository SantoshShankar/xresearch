from __future__ import annotations

import logging

import httpx

from src.core import config
from src.core.models import Trend, TrendSource, TopicDomain
from src.trends.base import BaseTrendSource

logger = logging.getLogger(__name__)

CRICAPI_MATCHES_URL = "https://api.cricapi.com/v1/currentMatches"


class CricketTrendsFetcher(BaseTrendSource):
    """Fetch live/recent cricket match data from CricAPI — free tier: 100 req/day."""

    name = "cricapi"

    async def fetch(self, domains: list[TopicDomain] | None = None, limit: int = 10) -> list[Trend]:
        if not config.CRICAPI_KEY:
            logger.warning("CRICAPI_KEY not set, skipping cricket trends")
            return []

        params = {"apikey": config.CRICAPI_KEY, "offset": 0}
        trends: list[Trend] = []

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(CRICAPI_MATCHES_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.error("CricAPI fetch failed: %s", e)
            return []

        if data.get("status") != "success":
            logger.error("CricAPI error: %s", data.get("status"))
            return []

        matches = data.get("data", [])
        for match in matches:
            name = match.get("name", "")
            status = match.get("status", "")

            title = f"{name} — {status}" if status else name
            description_parts = []
            for score in match.get("score", []):
                innings = score.get("inning", "")
                runs = score.get("r", 0)
                wickets = score.get("w", 0)
                overs = score.get("o", 0)
                description_parts.append(f"{innings}: {runs}/{wickets} ({overs} ov)")

            trends.append(Trend(
                title=title,
                description=" | ".join(description_parts),
                source=TrendSource.CRICAPI,
                domain=TopicDomain.CRICKET,
                metadata={
                    "match_id": match.get("id", ""),
                    "match_type": match.get("matchType", ""),
                    "teams": match.get("teams", []),
                    "venue": match.get("venue", ""),
                    "status": status,
                },
            ))

            if len(trends) >= limit:
                break

        return trends
