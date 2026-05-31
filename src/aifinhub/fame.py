"""Score each paper's relevance to the FAME project by embedding similarity.

The score is the cosine similarity (as a percentage) between the paper's
title+abstract and the FAME project summary in fame/FAME.md, using a local
sentence-transformers model (free, no API key). Papers at or above
FAME_THRESHOLD% are flagged FAME-relevant (a "FAME" badge on the hub).
"""

from __future__ import annotations

import re
from typing import Optional

from rich.console import Console

from .config import ROOT, DB_PATH
from .db import DB

console = Console()

FAME_THRESHOLD = 50                      # >= this % = FAME-relevant
MODEL_NAME = "all-MiniLM-L6-v2"
# Same-domain cosine sits in a narrow band; map it onto 0-100% so tangential
# papers read low and core papers read high (stable, not batch-dependent).
SIM_LO, SIM_HI = 0.32, 0.72
# Look for the renamed file first, then the original name.
SUMMARY_CANDIDATES = [ROOT / "fame" / "FAME.md", ROOT / "fame" / "FAME_summary.md"]


def _summary_path():
    for p in SUMMARY_CANDIDATES:
        if p.exists():
            return p
    return None


def _clean_md(text: str) -> str:
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"[#*_>|\-]", " ", text)
    return " ".join(text.split())


def _fame_vector(model, text):
    """Centroid of the project summary's paragraphs (handles the model's short
    context window by embedding paragraphs and mean-pooling)."""
    import numpy as np
    paras = [_clean_md(p) for p in re.split(r"\n\s*\n", text)]
    paras = [p for p in paras if len(p) > 40]
    if not paras:
        paras = [_clean_md(text)]
    vecs = model.encode(paras, normalize_embeddings=True)
    v = vecs.mean(axis=0)
    return v / (np.linalg.norm(v) + 1e-9)


def score_fame(limit: Optional[int] = None, rescore: bool = True,
               status: str = "all") -> dict:
    path = _summary_path()
    if not path:
        raise SystemExit("fame/FAME.md not found.")
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise SystemExit("pip install sentence-transformers")

    db = DB(DB_PATH)
    papers = [p for p in db.query(status=None if status == "all" else status)
              if (p.title or p.abstract) and (rescore or p.fame_score is None)]
    if limit:
        papers = papers[:limit]
    if not papers:
        console.print("[yellow]Nothing to score.[/yellow]")
        return {}

    console.print(f"Embedding {len(papers)} papers vs {path.name} with {MODEL_NAME}…")
    model = SentenceTransformer(MODEL_NAME)
    fame_vec = _fame_vector(model, path.read_text())

    texts = [f"{p.title}. {(p.abstract or '')[:2000]}" for p in papers]
    vecs = model.encode(texts, normalize_embeddings=True, batch_size=32,
                        show_progress_bar=False)
    sims = vecs @ fame_vec  # cosine (both normalized)

    dist: dict = {}
    for p, s in zip(papers, sims):
        norm = (float(s) - SIM_LO) / (SIM_HI - SIM_LO)
        pct = round(max(0.0, min(1.0, norm)) * 100)
        db.update_fields(p.fingerprint, fame_score=pct, fame_note="")
        bucket = (pct // 10) * 10
        dist[bucket] = dist.get(bucket, 0) + 1

    relevant = sum(n for b, n in dist.items() if b >= FAME_THRESHOLD - (FAME_THRESHOLD % 10))
    console.print(
        f"[bold green]Scored {len(papers)}[/bold green] · "
        f"FAME-relevant (≥{FAME_THRESHOLD}%): "
        f"[magenta]{len([p for p in db.query() if (p.fame_score or 0) >= FAME_THRESHOLD])}[/magenta]"
    )
    console.print("similarity %% distribution: " +
                  " ".join(f"{b}s:{dist[b]}" for b in sorted(dist)))
    console.print("Next: [bold]python -m aifinhub build-site[/bold]")
    return dist
