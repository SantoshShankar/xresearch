"""Deep arXiv fetcher — pulls top papers with abstracts, scores by interestingness."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import arxiv
import anthropic

from src.core import config

logger = logging.getLogger(__name__)

# Agentic AI search queries (high priority)
AGENTIC_QUERIES = [
    "agentic AI",
    "AI agent tool use",
    "LLM agent planning",
    "autonomous AI agent",
    "multi-agent LLM",
    "agent benchmark",
    "code generation agent",
    "reasoning agent",
]

# Broader trending AI categories
TRENDING_CATEGORIES = ["cs.AI", "cs.CL", "cs.LG", "cs.MA"]

# Top labs — papers from these get a rank boost
TOP_LABS = [
    "openai", "anthropic", "meta", "facebook", "fair",
    "google", "deepmind", "google brain", "apple",
    "deepseek", "microsoft", "microsoft research",
    "nvidia", "mistral",
]

# Breakthrough signal keywords in abstract
BREAKTHROUGH_KEYWORDS = [
    "state-of-the-art", "sota", "outperforms", "surpasses",
    "novel", "first to", "breakthrough", "paradigm",
    "significantly improves", "order of magnitude",
    "new architecture", "fundamentally", "revolutionary",
]

JUDGE_PROMPT = """You are an AI research expert. Rate this paper on how interesting and impactful it is.

Consider:
- Is this a genuine breakthrough or incremental improvement?
- Does it introduce a novel idea, architecture, or approach?
- Would the AI community be excited about this?
- Is it practically useful or just theoretical?

Title: {title}
Authors: {authors}
Categories: {categories}
Abstract: {abstract}

Rate from 1-10 where:
1-3: Incremental, routine work
4-5: Solid but expected progress
6-7: Notable contribution, interesting approach
8-9: Major breakthrough, significant impact
10: Field-defining, paradigm shift

Reply with ONLY a single number (1-10), nothing else."""


@dataclass
class ArxivPaper:
    title: str
    abstract: str
    authors: list[str]
    url: str
    pdf_url: str
    categories: list[str]
    published: str
    is_agentic: bool = False
    interest_score: float = 0.0
    score_breakdown: dict = field(default_factory=dict)


def fetch_agentic_papers(limit: int = 10) -> list[ArxivPaper]:
    """Fetch recent papers specifically about agentic AI."""
    query = " OR ".join(f'abs:"{q}"' for q in AGENTIC_QUERIES)
    return _search(query, limit, is_agentic=True)


def fetch_trending_papers(limit: int = 10) -> list[ArxivPaper]:
    """Fetch latest papers from top AI categories."""
    cat_query = " OR ".join(f"cat:{c}" for c in TRENDING_CATEGORIES)
    return _search(cat_query, limit, is_agentic=False)


def _search(query: str, limit: int, is_agentic: bool) -> list[ArxivPaper]:
    search = arxiv.Search(
        query=query,
        max_results=limit,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers: list[ArxivPaper] = []
    try:
        client = arxiv.Client()
        for result in client.results(search):
            papers.append(ArxivPaper(
                title=result.title,
                abstract=result.summary or "",
                authors=[a.name for a in result.authors[:5]],
                url=result.entry_id,
                pdf_url=result.pdf_url or "",
                categories=list(result.categories or []),
                published=result.published.isoformat() if result.published else "",
                is_agentic=is_agentic,
            ))
    except Exception as e:
        logger.error("arXiv search failed: %s", e)

    return papers


def _lab_boost(paper: ArxivPaper) -> float:
    """Score boost if authors are from a top lab. Returns 0-3."""
    authors_lower = " ".join(paper.authors).lower()
    title_lower = paper.title.lower()
    abstract_lower = paper.abstract[:500].lower()
    text = f"{authors_lower} {title_lower} {abstract_lower}"

    for lab in TOP_LABS:
        if lab in text:
            return 3.0
    return 0.0


def _keyword_boost(paper: ArxivPaper) -> float:
    """Score boost for breakthrough language in abstract. Returns 0-2."""
    abstract_lower = paper.abstract.lower()
    hits = sum(1 for kw in BREAKTHROUGH_KEYWORDS if kw in abstract_lower)
    return min(hits, 2)  # cap at 2


def _claude_judge_score(paper: ArxivPaper) -> float:
    """Use Claude to rate paper interestingness 1-10."""
    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        prompt = JUDGE_PROMPT.format(
            title=paper.title,
            authors=", ".join(paper.authors),
            categories=", ".join(paper.categories),
            abstract=paper.abstract[:1500],
        )
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=5,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        match = re.search(r"\d+", raw)
        if match:
            return float(min(int(match.group()), 10))
    except Exception as e:
        logger.error("Claude judge failed for '%s': %s", paper.title, e)
    return 5.0  # default middle score


def rank_papers(papers: list[ArxivPaper], top_k: int = 5) -> list[ArxivPaper]:
    """Score and rank papers by interestingness.

    Final score = claude_judge (0-10) + lab_boost (0-3) + keyword_boost (0-2) + agentic_boost (0-1)
    Max possible: 16
    """
    for paper in papers:
        judge = _claude_judge_score(paper)
        lab = _lab_boost(paper)
        keyword = _keyword_boost(paper)
        agentic = 1.0 if paper.is_agentic else 0.0

        paper.interest_score = judge + lab + keyword + agentic
        paper.score_breakdown = {
            "claude_judge": judge,
            "lab_boost": lab,
            "keyword_boost": keyword,
            "agentic_boost": agentic,
            "total": paper.interest_score,
        }
        logger.info(
            "Paper: %.50s | judge=%.0f lab=%.0f kw=%.0f agent=%.0f | total=%.1f",
            paper.title, judge, lab, keyword, agentic, paper.interest_score,
        )

    papers.sort(key=lambda p: p.interest_score, reverse=True)
    return papers[:top_k]
