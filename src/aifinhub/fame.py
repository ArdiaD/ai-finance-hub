"""Score every paper's relevance to the FAME research project (0-10).

Uses fame/FAME_summary.md as the rubric and an LLM to rate each paper. Papers at
or above FAME_THRESHOLD are flagged FAME-relevant (a "FAME" badge on the hub).
Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import json
from typing import Optional

from rich.console import Console

from .config import ROOT, DB_PATH, env
from .db import DB

console = Console()

FAME_THRESHOLD = 8                       # >= this = FAME-relevant (directly GenAI/LLM core)
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
SUMMARY_PATH = ROOT / "fame" / "FAME_summary.md"


def _summary() -> str:
    return SUMMARY_PATH.read_text() if SUMMARY_PATH.exists() else ""


def score_fame(limit: Optional[int] = None, model: str = DEFAULT_MODEL,
               status: str = "all", rescore: bool = False) -> dict:
    if not env("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set (add it to .env).")
    summary = _summary()
    if not summary:
        raise SystemExit(f"{SUMMARY_PATH} not found.")
    try:
        import anthropic
    except ImportError:
        raise SystemExit("pip install anthropic")

    db = DB(DB_PATH)
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    papers = [p for p in db.query(status=None if status == "all" else status)
              if p.abstract and (rescore or p.fame_score is None)]
    if limit:
        papers = papers[:limit]
    console.print(f"Scoring [bold]{len(papers)}[/bold] papers for FAME relevance "
                  f"with {model}…\n")

    dist: dict = {}
    for p in papers:
        prompt = (
            "Below is the description of a research project (FAME). Then a paper.\n\n"
            f"=== FAME PROJECT ===\n{summary}\n=== END ===\n\n"
            "Rate how relevant the paper is to the FAME project on a 0-10 scale "
            "(10 = squarely on FAME's core topics — Generative AI / LLMs for "
            "investing & trading, investor behavior & AI adoption, AI's effect on "
            "price formation/market efficiency, adversarial or regulatory AI risks; "
            "5 = adjacent AI-in-finance; 0 = unrelated). "
            'Respond with JSON only: {"score": <int 0-10>, "reason": "<one short '
            'sentence>"}.\n\n'
            f"PAPER\nTitle: {p.title}\nAbstract: {p.abstract[:1600]}"
        )
        try:
            msg = client.messages.create(
                model=model, max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text
            raw = raw[raw.find("{"): raw.rfind("}") + 1]
            data = json.loads(raw)
            sc = int(data["score"])
        except Exception as e:  # noqa: BLE001
            console.print(f"  [yellow]skip ({type(e).__name__}): {p.title[:40]}[/yellow]")
            continue
        db.update_fields(p.fingerprint, fame_score=sc,
                         fame_note=str(data.get("reason", ""))[:200])
        dist[sc] = dist.get(sc, 0) + 1
        tag = "[magenta]FAME[/magenta]" if sc >= FAME_THRESHOLD else "    "
        console.print(f"  {tag} {sc:>2}  {p.title[:54]}")

    relevant = sum(n for s, n in dist.items() if s >= FAME_THRESHOLD)
    console.print(f"\n[bold green]Scored {sum(dist.values())}[/bold green] · "
                  f"FAME-relevant (≥{FAME_THRESHOLD}): [magenta]{relevant}[/magenta]")
    console.print("Next: [bold]python -m aifinhub build-site[/bold]")
    return dist
