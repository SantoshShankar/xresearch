"""Rank trends using cosine similarity on titles + majority vote + recency boost."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.core.models import Trend, TopicDomain

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.35

# Recency half-life in hours — trends older than this lose half their score
RECENCY_HALF_LIFE_HOURS = 12


def _recency_weight(trend: Trend) -> float:
    """Exponential decay based on age. Recent = ~1.0, day old = ~0.25, week old = ~0.01."""
    now = datetime.now(timezone.utc)
    fetched = trend.fetched_at.replace(tzinfo=timezone.utc) if trend.fetched_at.tzinfo is None else trend.fetched_at

    # Check for published date in metadata (more accurate than fetch time)
    published_str = trend.metadata.get("published_at") or trend.metadata.get("published") or ""
    if published_str:
        try:
            published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            age_hours = (now - published).total_seconds() / 3600
        except (ValueError, TypeError):
            age_hours = (now - fetched).total_seconds() / 3600
    else:
        age_hours = (now - fetched).total_seconds() / 3600

    # Exponential decay: score = 2^(-age / half_life)
    return math.pow(2, -age_hours / RECENCY_HALF_LIFE_HOURS)


def rank_trends(
    trends: list[Trend],
    domain: TopicDomain,
    top_k: int = 3,
) -> list[Trend]:
    """Pick top_k trends for a domain using cosine similarity clustering + majority vote + recency.

    Scoring: cluster_score = source_count * 2 + avg_recency_weight * 3 + normalized_raw * 1
    This heavily favors trends that are (1) recent and (2) appear across multiple sources.
    """
    domain_trends = [t for t in trends if t.domain == domain]
    if not domain_trends:
        return []

    if len(domain_trends) <= top_k:
        return domain_trends

    # TF-IDF on titles
    titles = [t.title.lower() for t in domain_trends]
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(titles)
    sim_matrix = cosine_similarity(tfidf_matrix)

    # Cluster: greedy — assign each trend to a cluster
    clusters: list[list[int]] = []
    assigned: set[int] = set()

    for i in range(len(domain_trends)):
        if i in assigned:
            continue
        cluster = [i]
        assigned.add(i)
        for j in range(i + 1, len(domain_trends)):
            if j in assigned:
                continue
            if sim_matrix[i][j] >= SIMILARITY_THRESHOLD:
                cluster.append(j)
                assigned.add(j)
        clusters.append(cluster)

    # Normalize raw scores across all domain trends
    max_raw = max((t.raw_score for t in domain_trends), default=1.0) or 1.0

    # Score each cluster
    scored_clusters: list[tuple[float, list[int]]] = []
    for cluster in clusters:
        sources = set(domain_trends[i].source for i in cluster)
        source_count = len(sources)

        recency_weights = [_recency_weight(domain_trends[i]) for i in cluster]
        avg_recency = np.mean(recency_weights)
        max_recency = max(recency_weights)

        norm_raw = np.mean([domain_trends[i].raw_score / max_raw for i in cluster])

        # Weighted score: recency dominates, source diversity is important, raw score is minor
        score = (source_count * 2.0) + (max_recency * 3.0) + (norm_raw * 1.0)

        scored_clusters.append((score, cluster))

    scored_clusters.sort(key=lambda x: x[0], reverse=True)

    # Pick best representative from each top cluster (most recent)
    top_trends: list[Trend] = []
    for score, cluster in scored_clusters[:top_k]:
        best_idx = max(cluster, key=lambda i: _recency_weight(domain_trends[i]))
        trend = domain_trends[best_idx]
        sources_in_cluster = list(set(domain_trends[i].source.value for i in cluster))
        trend.metadata["cluster_size"] = len(cluster)
        trend.metadata["sources_in_cluster"] = sources_in_cluster
        trend.metadata["cluster_score"] = round(score, 2)
        trend.metadata["recency_weight"] = round(_recency_weight(trend), 3)
        top_trends.append(trend)

    return top_trends
