"""Keyword-based theme tagging.

Each theme in config.yaml maps to a list of keywords; a paper is tagged with a
theme if any of its keywords appears (case-insensitive substring) in the title
or abstract. Deterministic, fast, no API. A paper can carry several themes.
"""

from __future__ import annotations

from .models import Paper


def tag(paper: Paper, cfg: dict) -> list[str]:
    themes_cfg = cfg.get("themes", {})
    text = f"{paper.title}\n{paper.abstract}".lower()
    matched = [
        name for name, keywords in themes_cfg.items()
        if any(kw.lower() in text for kw in keywords)
    ]
    return matched


def tag_in_place(paper: Paper, cfg: dict) -> Paper:
    paper.themes = tag(paper, cfg)
    return paper


def retag_all() -> dict:
    """Re-apply the current theme taxonomy to every paper in the database."""
    import json
    from rich.console import Console
    from .config import load_config, DB_PATH
    from .db import DB

    console = Console()
    cfg = load_config()
    db = DB(DB_PATH)
    papers = db.query()
    counts: dict[str, int] = {}
    for p in papers:
        themes = tag(p, cfg)
        db.update_fields(p.fingerprint, themes=json.dumps(themes))
        for t in themes:
            counts[t] = counts.get(t, 0) + 1
    console.print(f"[green]Re-tagged {len(papers)} papers.[/green]")
    for t, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        console.print(f"  {n:3d}  {t}")
    return counts
