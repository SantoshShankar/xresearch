"""Fetch top arXiv AI papers, rank by interestingness, summarize, and send via iMessage."""

import logging
import os

from src.trends.arxiv_deep import (
    fetch_agentic_papers, fetch_trending_papers, rank_papers, ArxivPaper,
)
from src.core.db import save_paper_summary
from src.content.paper_summarizer import PaperSummarizer
from src.publisher.imessage import send_imessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("xresearch.papers")

from dotenv import load_dotenv
load_dotenv()

RECIPIENT = os.getenv("IMESSAGE_RECIPIENT", "")


def dedupe_papers(papers: list[ArxivPaper]) -> list[ArxivPaper]:
    seen: set[str] = set()
    unique: list[ArxivPaper] = []
    for p in papers:
        key = p.title.lower().strip()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def main():
    # 1. Fetch papers (cast a wide net)
    logger.info("Fetching agentic AI papers...")
    agentic = fetch_agentic_papers(limit=15)
    logger.info("Found %d agentic papers", len(agentic))

    logger.info("Fetching trending AI papers...")
    trending = fetch_trending_papers(limit=15)
    logger.info("Found %d trending papers", len(trending))

    all_papers = dedupe_papers(agentic + trending)
    logger.info("Total unique papers: %d", len(all_papers))

    if not all_papers:
        logger.warning("No papers found")
        return

    # 2. Rank by interestingness (Claude judge + lab boost + keywords)
    logger.info("Ranking papers by interestingness...")
    top_papers = rank_papers(all_papers, top_k=5)

    logger.info("Top %d papers selected:", len(top_papers))
    for p in top_papers:
        bd = p.score_breakdown
        logger.info(
            "  [%.1f] judge=%.0f lab=%.0f kw=%.0f agent=%.0f | %s",
            p.interest_score, bd["claude_judge"], bd["lab_boost"],
            bd["keyword_boost"], bd["agentic_boost"], p.title[:60],
        )

    # 3. Summarize top papers only
    logger.info("Generating summaries...")
    summarizer = PaperSummarizer()
    summaries = summarizer.summarize_batch(top_papers)
    logger.info("Summarized %d papers", len(summaries))

    # 4. Save to DB + send via iMessage
    total = len(summaries)
    for paper, summary in summaries:
        save_paper_summary(
            title=paper.title,
            authors=paper.authors,
            summary=summary,
            paper_url=paper.url,
            pdf_url=paper.pdf_url,
            categories=paper.categories,
            interest_score=paper.interest_score,
            score_breakdown=paper.score_breakdown,
            is_agentic=paper.is_agentic,
        )
    logger.info("Saved %d papers to DB", total)

    if not RECIPIENT:
        logger.warning("IMESSAGE_RECIPIENT not set — printing to stdout")
        for paper, summary in summaries:
            tag = "🤖 AGENTIC" if paper.is_agentic else "📄 AI"
            print(f"\n{tag} (score: {paper.interest_score:.1f}): {paper.title}")
            print(f"{summary}")
            print(f"🔗 {paper.url}")
        return

    sent = 0
    for i, (paper, summary) in enumerate(summaries, 1):
        tag = "🤖 AGENTIC AI" if paper.is_agentic else "📄 TRENDING AI"
        score = paper.interest_score
        bd = paper.score_breakdown

        lines = [
            f"[{i}/{total}] {tag} — Score: {score:.1f}/16",
            "",
            f"📑 {paper.title}",
            f"👥 {', '.join(paper.authors[:3])}",
            "",
            summary,
            "",
            f"🔗 {paper.url}",
        ]
        message = "\n".join(lines)

        if send_imessage(RECIPIENT, message):
            sent += 1

    logger.info("Sent %d/%d paper summaries to %s", sent, total, RECIPIENT)


if __name__ == "__main__":
    main()
