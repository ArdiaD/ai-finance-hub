"""Relevance scoring: cheap keyword gate, optional LLM re-ranking."""

from __future__ import annotations

import json
from typing import Optional

from .config import env
from .models import Paper


def _count_hits(text: str, terms: list[str]) -> list[str]:
    text = text.lower()
    return [t for t in terms if t.lower() in text]


def keyword_score(paper: Paper, cfg: dict) -> tuple[float, str]:
    """Score = (#ai_hits) + (#finance_hits), requiring >=1 of each.

    Returns (score, note). A score of 0 means it failed the AND gate.
    """
    rel = cfg["relevance"]
    text = f"{paper.title}\n{paper.abstract}"
    ai = _count_hits(text, rel["ai_terms"])
    fin = _count_hits(text, rel["finance_terms"])
    if not ai or not fin:
        return 0.0, "no AI×finance overlap"
    score = float(len(ai) + len(fin))
    note = f"AI: {', '.join(ai[:3])} | Finance: {', '.join(fin[:3])}"
    return score, note


def llm_score(paper: Paper, cfg: dict) -> Optional[tuple[float, str]]:
    """Re-rank with Claude on a 0–10 scale. Returns None if unavailable."""
    api_key = env("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        "You curate a research hub on AI applied to TRADING and INVESTMENT. "
        "Rate how relevant this paper is on a 0-10 scale (10 = core AI-driven "
        "trading/investing/asset-pricing methodology; 0 = unrelated). "
        "Respond with JSON only: {\"score\": <int>, \"reason\": \"<short>\"}.\n\n"
        f"Title: {paper.title}\nAbstract: {paper.abstract[:1500]}"
    )
    try:
        msg = client.messages.create(
            model=cfg["relevance"]["llm_model"],
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        text = text[text.find("{"): text.rfind("}") + 1]
        data = json.loads(text)
        return float(data["score"]), f"LLM: {data.get('reason', '')}"
    except Exception as e:  # noqa: BLE001 — never let scoring crash a run
        return None


def score_paper(paper: Paper, cfg: dict) -> Paper:
    score, note = keyword_score(paper, cfg)
    if score > 0 and cfg["relevance"].get("use_llm"):
        llm = llm_score(paper, cfg)
        if llm:
            score, note = llm[0], llm[1]
    paper.score = score
    paper.relevance_note = note
    return paper
