"""Simple JSON-based history tracker for dedup across pipeline runs.

Stores sent papers and posts in db/history.json so that GitHub Actions runs
can avoid re-sending the same content.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

HISTORY_PATH = Path(__file__).resolve().parent.parent.parent / "db" / "history.json"

_EMPTY: dict = {"papers": [], "posts": []}


def load_history() -> dict:
    """Read db/history.json. Returns empty structure if missing or corrupt."""
    if not HISTORY_PATH.exists():
        return {"papers": [], "posts": []}
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"papers": [], "posts": []}
        data.setdefault("papers", [])
        data.setdefault("posts", [])
        return data
    except Exception as e:
        logger.warning("Failed to load history from %s: %s", HISTORY_PATH, e)
        return {"papers": [], "posts": []}


def save_history(history: dict) -> None:
    """Write history to db/history.json, pruning entries older than 30 days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    history["papers"] = [
        p for p in history.get("papers", [])
        if p.get("sent_at", "") >= cutoff
    ]
    history["posts"] = [
        p for p in history.get("posts", [])
        if p.get("sent_at", "") >= cutoff
    ]

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(history, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Saved history: %d papers, %d posts", len(history["papers"]), len(history["posts"]))


def is_paper_sent(arxiv_id: str, history: dict) -> bool:
    """Check if a paper with this arxiv_id was already sent."""
    for p in history.get("papers", []):
        if p.get("arxiv_id") == arxiv_id:
            return True
    return False


def is_paper_sent_recently(arxiv_id: str, history: dict, days: int = 7) -> bool:
    """Check if a paper was sent within the last N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    for p in history.get("papers", []):
        if p.get("arxiv_id") == arxiv_id and p.get("sent_at", "") >= cutoff:
            return True
    return False


def record_paper(arxiv_id: str, title: str, score: float, history: dict) -> None:
    """Add a paper to the sent list."""
    history.setdefault("papers", []).append({
        "arxiv_id": arxiv_id,
        "title": title,
        "score": score,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    })


def record_post(trend_title: str, domain: str, history: dict) -> None:
    """Add a post to the sent list."""
    history.setdefault("posts", []).append({
        "trend_title": trend_title,
        "domain": domain,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    })
