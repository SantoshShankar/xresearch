"""Deep arXiv fetcher — pulls papers from arXiv + HuggingFace daily, ranks by interestingness.

Scoring formula (max 18):
    total = claude_judge (0-10) + social_signal (0-5) + lab_boost (0-2) + agentic_boost (0-1)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

import anthropic
import arxiv
import httpx

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

# Top labs — match against authors string only (not title/abstract)
TOP_LABS = [
    "openai", "anthropic", "meta ai", "facebook ai", "fair",
    "google research", "deepmind", "google brain", "apple",
    "deepseek", "microsoft research",
    "nvidia", "mistral", "allen institute", "ai2",
]

HF_DAILY_ENDPOINT = "https://huggingface.co/api/daily_papers"

JUDGE_PROMPT = """You are an AI research expert rating how interesting and impactful a paper is.

Score on 4 dimensions (1-10 each):
- novelty: Is the core idea genuinely new, or incremental?
- rigor: Is the evaluation thorough and honest?
- practical_impact: Will practitioners actually use this?
- agent_relevance: How relevant to AI agents / LLM systems / tool use?

Examples of high-quality papers (each would score ~9 overall):

Title: Memento
Abstract: We introduce Memento, a memory-augmented distillation method where a smaller model learns to cache and recall intermediate reasoning steps, matching larger model performance on long-horizon tasks.
Score: {{"novelty": 9, "rigor": 8, "practical_impact": 9, "agent_relevance": 9}}

Title: Terminal-Bench 2.0
Abstract: A redesigned benchmark for evaluating LLM coding agents in real terminal environments, with 300 tasks spanning debugging, refactoring, and system administration. We show frontier models achieve only 34% success.
Score: {{"novelty": 8, "rigor": 9, "practical_impact": 10, "agent_relevance": 10}}

Title: Memory Intelligence Agent (MIA)
Abstract: MIA is an agent architecture that actively manages a structured memory store, deciding what to remember, forget, and retrieve. On long-horizon benchmarks, MIA outperforms context-stuffing baselines by 23%.
Score: {{"novelty": 9, "rigor": 8, "practical_impact": 9, "agent_relevance": 10}}

Examples of low-quality papers (each would score ~3 overall):

Title: Improving BERT for Legal Document Classification
Abstract: We fine-tune BERT on a legal corpus and achieve 2% improvement over the baseline on a private dataset.
Score: {{"novelty": 2, "rigor": 4, "practical_impact": 3, "agent_relevance": 1}}

Title: A Survey of Graph Neural Networks
Abstract: We review existing work on graph neural networks and categorize methods by architecture type.
Score: {{"novelty": 2, "rigor": 5, "practical_impact": 3, "agent_relevance": 2}}

Now score this paper. Reply with ONLY a JSON object matching the schema above — no prose, no markdown fences.

Title: {title}
Authors: {authors}
Categories: {categories}
Abstract: {abstract}"""


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
    social_sources: list[str] = field(default_factory=list)
    judge_breakdown: dict = field(default_factory=dict)
    arxiv_id: str = ""


# ----- id normalization & dedup -----

_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})")


def _normalize_arxiv_id(url_or_id: str) -> str:
    """Extract canonical arxiv id (no version suffix) from url or raw id."""
    if not url_or_id:
        return ""
    m = _ARXIV_ID_RE.search(url_or_id)
    if m:
        return m.group(1)
    # fallback: last path segment, strip vN
    tail = url_or_id.rsplit("/", 1)[-1]
    return re.sub(r"v\d+$", "", tail)


def dedupe_by_id(papers: Iterable[ArxivPaper]) -> list[ArxivPaper]:
    """Merge duplicates by arxiv_id. Union social_sources; keep is_agentic OR-ed."""
    merged: dict[str, ArxivPaper] = {}
    orphans: list[ArxivPaper] = []
    for p in papers:
        pid = p.arxiv_id or _normalize_arxiv_id(p.url)
        if not pid:
            orphans.append(p)
            continue
        p.arxiv_id = pid
        if pid not in merged:
            merged[pid] = p
        else:
            existing = merged[pid]
            for src in p.social_sources:
                if src not in existing.social_sources:
                    existing.social_sources.append(src)
            existing.is_agentic = existing.is_agentic or p.is_agentic
            if not existing.abstract and p.abstract:
                existing.abstract = p.abstract
            if not existing.authors and p.authors:
                existing.authors = p.authors
            # preserve hf_upvotes if present
            if p.score_breakdown.get("hf_upvotes") and not existing.score_breakdown.get("hf_upvotes"):
                existing.score_breakdown["hf_upvotes"] = p.score_breakdown["hf_upvotes"]
    return list(merged.values()) + orphans


# ----- arXiv fetchers -----

def fetch_agentic_papers(limit: int = 15) -> list[ArxivPaper]:
    """Fetch recent papers specifically about agentic AI."""
    query = " OR ".join(f'abs:"{q}"' for q in AGENTIC_QUERIES)
    return _search(query, limit, is_agentic=True)


def fetch_trending_papers(limit: int = 15) -> list[ArxivPaper]:
    """Fetch latest papers from top AI categories."""
    cat_query = " OR ".join(f"cat:{c}" for c in TRENDING_CATEGORIES)
    return _search(cat_query, limit, is_agentic=False)


def fetch_recent_arxiv(days: int = 7, limit: int = 500) -> list[ArxivPaper]:
    """Fetch arXiv papers from the last N days across top AI categories."""
    cat_query = " OR ".join(f"cat:{c}" for c in TRENDING_CATEGORIES)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    papers: list[ArxivPaper] = []
    try:
        search = arxiv.Search(
            query=cat_query,
            max_results=limit,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        client = arxiv.Client(page_size=100, delay_seconds=1, num_retries=3)
        for result in client.results(search):
            if result.published and result.published < cutoff:
                break  # sorted desc — remaining are older
            papers.append(_arxiv_result_to_paper(result, is_agentic=False))
    except Exception as e:
        logger.error("fetch_recent_arxiv failed: %s", e)
    logger.info("fetch_recent_arxiv: %d papers in last %d days", len(papers), days)
    return papers


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
            papers.append(_arxiv_result_to_paper(result, is_agentic=is_agentic))
    except Exception as e:
        logger.error("arXiv search failed: %s", e)
    return papers


def _arxiv_result_to_paper(result, is_agentic: bool) -> ArxivPaper:
    url = result.entry_id or ""
    return ArxivPaper(
        title=(result.title or "").strip(),
        abstract=result.summary or "",
        authors=[a.name for a in result.authors[:5]],
        url=url,
        pdf_url=result.pdf_url or "",
        categories=list(result.categories or []),
        published=result.published.isoformat() if result.published else "",
        is_agentic=is_agentic,
        arxiv_id=_normalize_arxiv_id(url),
    )


# ----- HuggingFace daily papers -----

def fetch_huggingface_papers(days: int = 7) -> list[ArxivPaper]:
    """Scrape HuggingFace daily papers (curated social-signal source)."""
    papers: list[ArxivPaper] = []
    seen: set[str] = set()
    try:
        with httpx.Client(follow_redirects=True, timeout=20.0) as client:
            for delta in range(days):
                date_str = (datetime.now(timezone.utc) - timedelta(days=delta)).strftime("%Y-%m-%d")
                try:
                    resp = client.get(HF_DAILY_ENDPOINT, params={"date": date_str})
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                except Exception as e:
                    logger.debug("HF daily %s failed: %s", date_str, e)
                    continue
                if not isinstance(data, list):
                    continue
                for item in data:
                    paper = _parse_hf_item(item)
                    if paper and paper.arxiv_id and paper.arxiv_id not in seen:
                        seen.add(paper.arxiv_id)
                        papers.append(paper)
    except Exception as e:
        logger.error("fetch_huggingface_papers failed: %s", e)
        return []
    logger.info("fetch_huggingface_papers: %d unique papers in last %d days", len(papers), days)
    return papers


def _parse_hf_item(item: dict) -> ArxivPaper | None:
    """Robustly parse a HF daily papers API item."""
    if not isinstance(item, dict):
        return None
    # The payload nests under "paper" in the common shape.
    p = item.get("paper") if isinstance(item.get("paper"), dict) else item
    arxiv_id = p.get("id") or p.get("arxiv_id") or ""
    arxiv_id = _normalize_arxiv_id(str(arxiv_id))
    if not arxiv_id:
        return None
    title = (p.get("title") or item.get("title") or "").strip()
    abstract = p.get("summary") or p.get("abstract") or ""
    upvotes = p.get("upvotes") or item.get("upvotes") or 0
    raw_authors = p.get("authors") or []
    authors: list[str] = []
    for a in raw_authors[:5]:
        if isinstance(a, str):
            authors.append(a)
        elif isinstance(a, dict):
            name = a.get("name") or a.get("fullname") or ""
            if name:
                authors.append(name)
    url = f"http://arxiv.org/abs/{arxiv_id}"
    pdf_url = f"http://arxiv.org/pdf/{arxiv_id}"
    return ArxivPaper(
        title=title,
        abstract=abstract,
        authors=authors,
        url=url,
        pdf_url=pdf_url,
        categories=[],
        published=item.get("publishedAt") or "",
        is_agentic=False,
        social_sources=["huggingface_daily"],
        score_breakdown={"hf_upvotes": int(upvotes) if upvotes else 0},
        arxiv_id=arxiv_id,
    )


# ----- ranking -----

_WORD_BOUNDARY_LAB_RES = [(lab, re.compile(r"\b" + re.escape(lab) + r"\b", re.I)) for lab in TOP_LABS]


def _lab_boost(paper: ArxivPaper) -> float:
    """Match lab names only in the authors string. Returns 0 or 2.0."""
    authors_str = " ".join(paper.authors)
    if not authors_str:
        return 0.0
    for _lab, rex in _WORD_BOUNDARY_LAB_RES:
        if rex.search(authors_str):
            return 2.0
    return 0.0


def _social_signal_boost(paper: ArxivPaper) -> float:
    """Dominant signal: curated sources (HF daily, etc). Returns 0-5."""
    if not paper.social_sources:
        return 0.0
    score = 0.0
    if "huggingface_daily" in paper.social_sources:
        score += 4.0
    # any additional sources add +1 each
    extras = [s for s in paper.social_sources if s != "huggingface_daily"]
    score += float(len(extras))
    return min(score, 5.0)


def _extract_json(raw: str) -> dict | None:
    raw = raw.strip()
    # strip markdown fence
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        pass
    # regex fallback — grab first {...} block
    m = re.search(r"\{[^{}]*\}", raw)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            return None
    return None


def _claude_judge_score(paper: ArxivPaper) -> float:
    """Use Claude to rate the paper on 4 dimensions. Returns mean (0-10)."""
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
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        data = _extract_json(raw)
        if not data:
            logger.warning("Judge returned unparseable output for %r: %s", paper.title[:60], raw[:120])
            return 5.0
        dims = ["novelty", "rigor", "practical_impact", "agent_relevance"]
        vals: list[float] = []
        for d in dims:
            v = data.get(d)
            if isinstance(v, (int, float)):
                vals.append(float(min(max(v, 1), 10)))
        if not vals:
            return 5.0
        paper.judge_breakdown = {d: data.get(d) for d in dims}
        return sum(vals) / len(vals)
    except Exception as e:
        logger.error("Claude judge failed for %r: %s", paper.title[:60], e)
    return 5.0


def _dedup_boost(paper: ArxivPaper, history: dict) -> float:
    """Return -10.0 if the paper was sent in the last 7 days, else 0.0."""
    from src.core.history import is_paper_sent_recently

    arxiv_id = paper.arxiv_id or _normalize_arxiv_id(paper.url)
    if arxiv_id and is_paper_sent_recently(arxiv_id, history, days=7):
        return -10.0
    return 0.0


def rank_papers(papers: list[ArxivPaper], top_k: int = 5, history: dict | None = None) -> list[ArxivPaper]:
    """Score and rank papers by interestingness.

    Two-pass ranking to avoid calling Claude judge on 500+ papers:
      1. Pre-filter using cheap signals (social, lab, agentic, dedup) → keep top 30
      2. Score shortlist with Claude judge → final ranking

    Final score = claude_judge (0-10) + social_signal (0-5) + lab_boost (0-2) + agentic_boost (0-1) + dedup
    Max possible: 18 (dedup can subtract 10 for recently-sent papers)
    """
    SHORTLIST_SIZE = 30

    # Pass 1: cheap signals only — no API calls
    for paper in papers:
        social = _social_signal_boost(paper)
        lab = _lab_boost(paper)
        agentic = 1.0 if paper.is_agentic else 0.0
        dedup = _dedup_boost(paper, history) if history is not None else 0.0

        paper.interest_score = social + lab + agentic + dedup
        paper.score_breakdown.update({
            "social_signal": social,
            "lab_boost": lab,
            "agentic_boost": agentic,
            "dedup_boost": dedup,
        })

    papers.sort(key=lambda p: p.interest_score, reverse=True)
    shortlist = papers[:SHORTLIST_SIZE]
    logger.info("Pre-filtered %d → %d candidates for Claude judge", len(papers), len(shortlist))

    # Pass 2: Claude judge on shortlist only
    for paper in shortlist:
        judge = _claude_judge_score(paper)
        paper.interest_score += judge
        paper.score_breakdown.update({
            "claude_judge": judge,
            "total": paper.interest_score,
        })
        logger.info(
            "Paper: %.50s | judge=%.1f social=%.1f lab=%.1f agent=%.0f dedup=%.0f | total=%.1f",
            paper.title, judge,
            paper.score_breakdown.get("social_signal", 0),
            paper.score_breakdown.get("lab_boost", 0),
            paper.score_breakdown.get("agentic_boost", 0),
            paper.score_breakdown.get("dedup_boost", 0),
            paper.interest_score,
        )

    shortlist.sort(key=lambda p: p.interest_score, reverse=True)
    return shortlist[:top_k]
