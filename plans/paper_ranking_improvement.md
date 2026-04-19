# Plan: Improve Paper Ranking Quality

## Validation set

**Week of 2026-04-06:**
- Efficient Agents
- Terminal-Bench 2.0
- AI IDEs vs Autonomous Agents
- Learning to Discover at Test Time
- Rethinking Multi-Agent Workflows
- Memory Control for Long-Horizon Agents
- Self-Correcting Multi-Agent LLM for Physics

**Week of 2026-04-13:**
- Memento
- Neural Computers
- The Universal Verifier
- Agent Skills in the Wild
- Memory Intelligence Agent (MIA)
- Single-Agent vs Multi-Agent LLMs
- Scaling Coding Agents via Atomic Skills

## Diagnosis

Looking at `src/trends/arxiv_deep.py` against the validation set, three compounding failures:

**1. Retrieval is the dominant problem, not ranking.** The judge can only rank what you fetch. Today the pipeline pulls 30 papers sorted by `SubmittedDate` — a ~6-hour slice of the arXiv firehose, not a week. The validation papers (Memento, Terminal-Bench 2.0, Efficient Agents, MIA) are HuggingFace-daily-tier curated picks that mostly wouldn't be in any random 30-paper window of the last few hours. Sampling from the wrong distribution.

**2. No curation signal.** Every validation paper surfaces on HuggingFace daily papers, alphaXiv trending, or AI Twitter — i.e., papers with *social signal*. The current ranker has zero access to that signal and tries to reconstruct "good paper" from abstract text alone.

**3. Ranking heuristics are noisy or adversarial.**
- `_lab_boost`: substring match on concatenated author+title+abstract text. "meta" hits "meta-learning", "apple" hits "Apple Silicon", "fair" hits "fair comparison". Binary 0/3, no partial credit.
- `_keyword_boost`: "state-of-the-art", "outperforms", "novel" rewards marketing language — the opposite of the validation set (Memento, MIA, Neural Computers have restrained titles).
- `agentic_boost` (+1): based on which query retrieved it, not actual relevance.
- Claude judge: zero-shot, integer 1-10, no rubric, no calibration. Empirically clusters in 5-7.

## Plan

### Phase 1 — Build an eval harness first (keystone)

Can't improve ranking without a feedback loop. Before touching anything else:

- Hardcode validation set as `{week_start: [titles]}` in `tests/eval_paper_ranking.py`.
- Script replays retrieval over a given date range, runs the ranker, computes **recall@5**, **recall@10**, **MRR** against the validation set. Fuzzy title match (normalized lowercase + Levenshtein ≤ 3).
- Baseline the current system on both weeks. Likely recall@5 is ~0-15%. That's the number to beat.

Everything downstream gets measured against this.

### Phase 2 — Fix retrieval (biggest lever)

Add curated sources where validation papers actually live:

- **HuggingFace daily papers** (`huggingface.co/papers`) — the canonical "best AI papers today" feed. Memento, Terminal-Bench, Efficient Agents typically land here. Scrape or use JSON endpoint.
- **alphaXiv trending** — social-signal layer over arXiv, 7-day window.
- **Papers With Code trending** — star-count signal.
- **HN front page filter** — any HN story linking to arxiv.org/abs/ in the last week, weighted by points.
- **Expand arXiv window**: instead of `max_results=100` sorted by date (6-hour slice), paginate 500 results across `cs.AI/CL/LG/MA` for the last 7 days to cover the full weekly cycle.
- **Dedup by arxiv_id**, not title prefix. Cross-source dedup as merge step.

Tradeoff: HF daily and alphaXiv are scraped, not API-stable. Accept the maintenance cost — it's where the signal is.

### Phase 3 — Fix ranking

In priority order:

1. **Social-signal boost (new, dominant).** If a paper appeared in HF daily OR HN front page OR PWC trending, worth more than any abstract-text heuristic. Likely moves recall@5 more than anything else.
2. **Delete `_keyword_boost`.** Anti-signal that rewards marketing language.
3. **Rewrite the Claude judge** with a few-shot rubric: include 3 validation papers labeled "9/10" with rationale, plus 3 low-quality papers labeled "3/10". Score on 4 dimensions (novelty, rigor, practical impact, agent-relevance). Return structured JSON. Current prompt asks for "a single number" with no anchoring — that's why it clusters.
4. **Replace `_lab_boost` substring match.** Two options: (a) pull affiliations from arXiv's `<affiliation>` field when present, or (b) one-shot LLM call to extract affiliations from the first-page author block. Per-lab partial credit, not binary.
5. *(Optional, bigger lift)* **Pairwise tournament ranking.** After phase-2 retrieval gives ~100 candidates, run a Claude-as-judge pairwise tournament on the top 20. Absolute scoring is noisy at 1-10 granularity; pairwise is more stable. Only do this if 3.1–3.4 doesn't hit the recall target.

### Phase 4 — Calibrate and iterate

- Re-run eval harness. Target: **recall@5 ≥ 60%** (≈8/14), recall@10 ≥ 80%.
- Iterate on whichever layer has the biggest gap between theoretical ceiling and actual contribution.

## Recommendation

**Do Phase 1 + Phase 2 first, then measure before touching Phase 3.** Strong prior: adding HuggingFace daily papers alone will surface 60-80% of the validation set, at which point ranking tweaks become polish, not rescue. Current ranker isn't great, but it's not the binding constraint — retrieval is.
