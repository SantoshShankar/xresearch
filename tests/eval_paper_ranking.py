"""Evaluation harness for the paper ranking pipeline.

Measures how well `rank_papers` surfaces a known-good validation set of papers.
Matching is by arxiv ID — no fragile keyword/title heuristics.
Metrics: recall@5, recall@10, MRR. See plans/paper_ranking_improvement.md.

Usage:
    PYTHONPATH=. python tests/eval_paper_ranking.py              # full eval (new pipeline)
    PYTHONPATH=. python tests/eval_paper_ranking.py --quick      # skip Claude judge
    PYTHONPATH=. python tests/eval_paper_ranking.py --week week2 --quick
    PYTHONPATH=. python tests/eval_paper_ranking.py --baseline --quick  # old pipeline
"""

from __future__ import annotations

import argparse
import logging
import sys

from src.trends import arxiv_deep
from src.trends.arxiv_deep import (
    ArxivPaper,
    _normalize_arxiv_id,
    dedupe_by_id,
    fetch_agentic_papers,
    fetch_huggingface_papers,
    fetch_recent_arxiv,
    fetch_trending_papers,
    rank_papers,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("eval_papers")


# ----- validation set: arxiv IDs, no keywords -----

VALIDATION_SET: dict[str, dict[str, str]] = {
    # Week of April 6-12, 2026
    "2026-04-06": {
        "2604.06425": "Neural Computers",
        "2604.04503": "Memory Intelligence Agent (MIA)",
        "2604.02460": "Single-Agent vs Multi-Agent LLMs",
        "2604.06240": "The Universal Verifier",
        "2604.05013": "Scaling Coding Agents via Atomic Skills",
        "2604.04323": "Agent Skills in the Wild",
        "2604.05081": "LightThinker++",
        "2601.21343": "Thinking Mid-training",
    },
    # Week of March 30 - April 5 (placeholder — add IDs when available)
    # "2026-03-30": {},
}

WEEK_ALIAS = {"week1": "2026-03-30", "week2": "2026-04-06"}


# ----- evaluation -----

def evaluate(all_candidates: list[ArxivPaper], ranked_papers: list[ArxivPaper], week: str) -> dict:
    """Evaluate retrieval (full pool) and ranking (scored list) separately."""
    validation = VALIDATION_SET.get(week, {})
    if not validation:
        return {
            "week": week, "n_validation": 0,
            "recall_at_5": 0.0, "recall_at_10": 0.0, "mrr": 0.0,
            "hits": [], "misses": [],
            "retrieval_hits": [], "retrieval_misses": [],
        }

    val_ids = set(validation.keys())

    # Retrieval recall: did the paper appear in the full candidate pool?
    pool_ids = {(_normalize_arxiv_id(p.url) or p.arxiv_id) for p in all_candidates}
    retrieval_hits = [(validation[aid], aid) for aid in val_ids if aid in pool_ids]
    retrieval_misses = [(validation[aid], aid) for aid in val_ids if aid not in pool_ids]

    # Ranking metrics: where did validation papers end up in the scored list?
    hits: list[tuple[str, int]] = []
    matched_ids: set[str] = set()
    for rank, paper in enumerate(ranked_papers, 1):
        pid = _normalize_arxiv_id(paper.url) or paper.arxiv_id
        if pid in val_ids and pid not in matched_ids:
            hits.append((validation[pid], rank))
            matched_ids.add(pid)

    misses = [(validation[aid], aid) for aid in val_ids if aid not in matched_ids]

    n = len(val_ids)
    reciprocal_ranks = []
    for aid in val_ids:
        found = next((r for name, r in hits if name == validation[aid]), None)
        reciprocal_ranks.append(1.0 / found if found else 0.0)

    return {
        "week": week,
        "n_validation": n,
        "recall_at_5": sum(1 for _, r in hits if r <= 5) / n if n else 0.0,
        "recall_at_10": sum(1 for _, r in hits if r <= 10) / n if n else 0.0,
        "mrr": sum(reciprocal_ranks) / n if n else 0.0,
        "hits": hits,
        "misses": misses,
        "retrieval_hits": retrieval_hits,
        "retrieval_misses": retrieval_misses,
    }


def print_report(reports: list[dict], mode: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"PAPER RANKING EVAL REPORT ({mode})")
    print("=" * 60)
    for r in reports:
        print(f"\n--- {r['week']} ({r['n_validation']} validation papers) ---")
        n_ret = len(r.get("retrieval_hits", []))
        n_ret_miss = len(r.get("retrieval_misses", []))
        print(f"  retrieval: {n_ret}/{n_ret + n_ret_miss} papers found in candidate pool")
        print(f"  recall@5:  {r['recall_at_5']:.2%}")
        print(f"  recall@10: {r['recall_at_10']:.2%}")
        print(f"  MRR:       {r['mrr']:.3f}")
        if r["hits"]:
            print("  Ranked hits:")
            for name, rank in sorted(r["hits"], key=lambda x: x[1]):
                print(f"    [{rank:3d}] {name}")
        if r.get("retrieval_misses"):
            print("  Not retrieved (never in candidate pool):")
            for name, aid in r["retrieval_misses"]:
                print(f"    [---] {name} ({aid})")
        misses_in_pool = [(n, a) for n, a in r["misses"]
                          if a not in {aid for _, aid in r.get("retrieval_misses", [])}]
        if misses_in_pool:
            print("  Retrieved but ranked below cutoff:")
            for name, aid in misses_in_pool:
                print(f"    [low] {name} ({aid})")
    print("=" * 60 + "\n")


# ----- runners -----

def run_new_pipeline(weeks: list[str], quick: bool) -> list[dict]:
    """Run the improved pipeline: HF daily + 7-day arXiv + agentic queries."""
    if quick:
        logger.info("--quick: monkey-patching _claude_judge_score to constant 5.0")
        arxiv_deep._claude_judge_score = lambda paper: 5.0  # type: ignore

    logger.info("Fetching HuggingFace daily papers (14 days)...")
    hf = fetch_huggingface_papers(days=14)
    logger.info("HF daily: %d papers", len(hf))

    logger.info("Fetching recent arXiv (14 days)...")
    recent = fetch_recent_arxiv(days=14, limit=500)
    logger.info("Recent arXiv: %d papers", len(recent))

    logger.info("Fetching agentic papers...")
    agentic = fetch_agentic_papers(limit=50)
    logger.info("Agentic: %d papers", len(agentic))

    all_papers = dedupe_by_id(hf + recent + agentic)
    logger.info("Total unique after dedup: %d", len(all_papers))

    logger.info("Ranking all papers...")
    ranked = rank_papers(all_papers, top_k=len(all_papers))

    return [evaluate(all_papers, ranked, week) for week in weeks]


def run_baseline(weeks: list[str], quick: bool) -> list[dict]:
    """Run the old pipeline: small arXiv window, no HF daily."""
    if quick:
        logger.info("--quick: monkey-patching _claude_judge_score to constant 5.0")
        arxiv_deep._claude_judge_score = lambda paper: 5.0  # type: ignore

    logger.info("Fetching agentic + trending (old pipeline)...")
    agentic = fetch_agentic_papers(limit=50)
    trending = fetch_trending_papers(limit=50)

    seen: set[str] = set()
    unique: list[ArxivPaper] = []
    for p in agentic + trending:
        key = p.title.lower().strip()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(p)
    logger.info("Old pipeline: %d unique papers", len(unique))

    logger.info("Ranking all papers...")
    ranked = rank_papers(unique, top_k=len(unique))

    return [evaluate(unique, ranked, week) for week in weeks]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Skip Claude judge (constant 5.0)")
    parser.add_argument("--baseline", action="store_true", help="Run old pipeline instead of new")
    parser.add_argument("--week", default="all", help="week2 or all")
    args = parser.parse_args()

    if args.week == "all":
        weeks = [w for w in VALIDATION_SET if VALIDATION_SET[w]]
    else:
        week = WEEK_ALIAS.get(args.week, args.week)
        if week not in VALIDATION_SET:
            print(f"Unknown week: {args.week}. Valid: {list(WEEK_ALIAS.keys())}", file=sys.stderr)
            sys.exit(1)
        weeks = [week]

    if args.baseline:
        reports = run_baseline(weeks, args.quick)
        print_report(reports, "BASELINE (old pipeline)")
    else:
        reports = run_new_pipeline(weeks, args.quick)
        print_report(reports, "NEW PIPELINE")


if __name__ == "__main__":
    main()
