"""Fetch top arXiv AI papers, rank by interestingness, summarize, and send via iMessage."""

import logging
import os

from src.trends.arxiv_deep import (
    fetch_agentic_papers, fetch_recent_arxiv, fetch_huggingface_papers,
    rank_papers, dedupe_by_id, ArxivPaper,
)
from src.core.db import save_paper_summary
from src.content.paper_summarizer import PaperSummarizer
from src.publisher.imessage import send_imessage
from src.publisher.email_publisher import send_papers_email
from src.publisher.telegram_publisher import send_papers_telegram

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
    # 1. Fetch papers from multiple sources (cast a wide net)
    logger.info("Fetching HuggingFace daily papers...")
    hf_papers = fetch_huggingface_papers(days=1)
    logger.info("Found %d HF daily papers", len(hf_papers))

    logger.info("Fetching recent arXiv papers (last 7 days)...")
    recent = fetch_recent_arxiv(days=1, limit=500)
    logger.info("Found %d recent arXiv papers", len(recent))

    logger.info("Fetching agentic AI papers...")
    agentic = fetch_agentic_papers(limit=15)
    logger.info("Found %d agentic papers", len(agentic))

    all_papers = dedupe_by_id(hf_papers + recent + agentic)
    logger.info("Total unique papers after dedup: %d", len(all_papers))

    if not all_papers:
        logger.warning("No papers found")
        return

    # 2. Rank by interestingness (Claude judge + social signal + lab boost)
    logger.info("Ranking papers by interestingness...")
    top_papers = rank_papers(all_papers, top_k=5)

    logger.info("Top %d papers selected:", len(top_papers))
    for p in top_papers:
        bd = p.score_breakdown
        logger.info(
            "  [%.1f] judge=%.1f social=%.1f lab=%.0f agent=%.0f | %s",
            p.interest_score, bd["claude_judge"], bd.get("social_signal", 0),
            bd["lab_boost"], bd["agentic_boost"], p.title[:60],
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

    # Deliver via available channels
    delivered = False

    if send_papers_telegram(summaries):
        delivered = True

    if send_papers_email(summaries):
        delivered = True

    # iMessage (macOS only)
    if RECIPIENT:
        sent = 0
        for i, (paper, summary) in enumerate(summaries, 1):
            tag = "🤖 AGENTIC AI" if paper.is_agentic else "📄 TRENDING AI"
            score = paper.interest_score

            lines = [
                f"[{i}/{total}] {tag} — Score: {score:.1f}/18",
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
        logger.info("Sent %d/%d paper summaries via iMessage to %s", sent, total, RECIPIENT)
        delivered = True

    if not delivered:
        logger.warning("No delivery method configured — printing to stdout")
        for paper, summary in summaries:
            tag = "🤖 AGENTIC" if paper.is_agentic else "📄 AI"
            print(f"\n{tag} (score: {paper.interest_score:.1f}): {paper.title}")
            print(f"{summary}")
            print(f"🔗 {paper.url}")


if __name__ == "__main__":
    main()
