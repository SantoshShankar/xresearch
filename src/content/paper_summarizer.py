"""Summarize arXiv papers into concise iMessage-friendly summaries using Claude."""

from __future__ import annotations

import logging

import anthropic

from src.core import config
from src.trends.arxiv_deep import ArxivPaper

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = """You are an AI researcher who explains papers to a technical but busy audience.

Given this arXiv paper, write a concise summary (3-5 sentences max) that covers:
1. What problem it solves
2. The key insight or method
3. Why it matters (practical impact)

Keep it sharp and accessible — no jargon without explanation. Write like you're texting a smart friend about an exciting paper.

Title: {title}
Authors: {authors}
Categories: {categories}
Abstract: {abstract}

Write ONLY the summary, nothing else."""


class PaperSummarizer:
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.model = model

    def summarize(self, paper: ArxivPaper) -> str:
        prompt = SUMMARY_PROMPT.format(
            title=paper.title,
            authors=", ".join(paper.authors),
            categories=", ".join(paper.categories),
            abstract=paper.abstract[:1500],
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error("Summary generation failed for '%s': %s", paper.title, e)
            return paper.abstract[:200] + "..."

    def summarize_batch(self, papers: list[ArxivPaper]) -> list[tuple[ArxivPaper, str]]:
        results = []
        for paper in papers:
            summary = self.summarize(paper)
            results.append((paper, summary))
        return results
