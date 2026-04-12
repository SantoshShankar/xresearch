"""SQLite storage for sent posts and paper summaries."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from src.core.config import DB_PATH


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            hashtags TEXT DEFAULT '',
            domain TEXT NOT NULL,
            source TEXT DEFAULT '',
            trend_title TEXT DEFAULT '',
            trend_url TEXT DEFAULT '',
            post_type TEXT DEFAULT 'trend',
            score REAL DEFAULT 0,
            metadata TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS paper_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            authors TEXT DEFAULT '',
            summary TEXT NOT NULL,
            paper_url TEXT DEFAULT '',
            pdf_url TEXT DEFAULT '',
            categories TEXT DEFAULT '',
            interest_score REAL DEFAULT 0,
            score_breakdown TEXT DEFAULT '{}',
            is_agentic INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
    """)
    conn.close()


def save_post(
    content: str,
    hashtags: list[str],
    domain: str,
    source: str,
    trend_title: str,
    trend_url: str,
    post_type: str = "trend",
    score: float = 0,
    metadata: dict | None = None,
) -> int:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO posts (content, hashtags, domain, source, trend_title, trend_url,
           post_type, score, metadata, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            content,
            " ".join(hashtags),
            domain,
            source,
            trend_title,
            trend_url,
            post_type,
            score,
            json.dumps(metadata or {}),
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def save_paper_summary(
    title: str,
    authors: list[str],
    summary: str,
    paper_url: str,
    pdf_url: str,
    categories: list[str],
    interest_score: float,
    score_breakdown: dict,
    is_agentic: bool,
) -> int:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO paper_summaries (title, authors, summary, paper_url, pdf_url,
           categories, interest_score, score_breakdown, is_agentic, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            title,
            ", ".join(authors),
            summary,
            paper_url,
            pdf_url,
            ", ".join(categories),
            interest_score,
            json.dumps(score_breakdown),
            1 if is_agentic else 0,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_posts(domain: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    conn = _get_conn()
    if domain:
        rows = conn.execute(
            "SELECT * FROM posts WHERE domain = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (domain, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM posts ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_paper_summaries(agentic_only: bool = False, limit: int = 50, offset: int = 0) -> list[dict]:
    conn = _get_conn()
    if agentic_only:
        rows = conn.execute(
            "SELECT * FROM paper_summaries WHERE is_agentic = 1 ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM paper_summaries ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_post_count(domain: str | None = None) -> int:
    conn = _get_conn()
    if domain:
        row = conn.execute("SELECT COUNT(*) FROM posts WHERE domain = ?", (domain,)).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM posts").fetchone()
    conn.close()
    return row[0]


def get_paper_count(agentic_only: bool = False) -> int:
    conn = _get_conn()
    if agentic_only:
        row = conn.execute("SELECT COUNT(*) FROM paper_summaries WHERE is_agentic = 1").fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM paper_summaries").fetchone()
    conn.close()
    return row[0]


# Initialize on import
init_db()
