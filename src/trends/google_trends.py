from __future__ import annotations

import logging
from xml.etree import ElementTree

import httpx

from src.core.models import Trend, TrendSource, TopicDomain
from src.trends.base import BaseTrendSource

logger = logging.getLogger(__name__)

# Google Trends RSS — free, no auth, real-time
GOOGLE_TRENDS_RSS = "https://trends.google.com/trending/rss?geo={geo}"


class GoogleTrendsFetcher(BaseTrendSource):
    name = "google_trends"

    def __init__(self, geo: str = "US"):
        self.geo = geo

    async def fetch(self, domains: list[TopicDomain] | None = None, limit: int = 10) -> list[Trend]:
        url = GOOGLE_TRENDS_RSS.format(geo=self.geo)
        trends: list[Trend] = []

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Google Trends RSS fetch failed: %s", e)
            return []

        try:
            root = ElementTree.fromstring(resp.text)
            items = root.findall(".//item")
        except ElementTree.ParseError as e:
            logger.error("Google Trends RSS parse failed: %s", e)
            return []

        for item in items[:limit * 2]:  # fetch extra, filter later
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            traffic = item.findtext("{https://trends.google.com/trending/rss}approx_traffic", "")

            domain = self._classify_domain(title)
            # Google Trends is a general signal — include all, let aggregator rank
            if domains and domain not in domains and TopicDomain.GENERAL not in domains:
                continue

            raw_score = self._parse_traffic(traffic)
            trends.append(Trend(
                title=title,
                url=link,
                source=TrendSource.GOOGLE_TRENDS,
                domain=domain,
                raw_score=raw_score,
                score=0.0,  # normalized later by aggregator
                metadata={"geo": self.geo, "traffic": traffic},
            ))

            if len(trends) >= limit:
                break

        return trends

    @staticmethod
    def _parse_traffic(traffic: str) -> float:
        """Parse traffic string like '500,000+' into a number."""
        if not traffic:
            return 0.0
        cleaned = traffic.replace(",", "").replace("+", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
