"""Fetch orchestration: run sources, score, dedup, store pending items."""

from __future__ import annotations

from rapidfuzz import fuzz
from rich.console import Console

from .config import load_config, DB_PATH
from .db import DB
from .models import Paper
from .relevance import score_paper
from .sources import REGISTRY
from .themes import tag_in_place

console = Console()

# Two distinct papers rarely share a >=92-similarity title; below that we treat
# near-identical titles (e.g. preprint vs published) as the same work.
FUZZY_THRESHOLD = 92


def _is_duplicate(paper: Paper, existing_titles: list[tuple[str, str]]) -> bool:
    nt = paper.norm_title
    for _, title in existing_titles:
        other = title.lower()
        if fuzz.token_sort_ratio(nt, other) >= FUZZY_THRESHOLD:
            return True
    return False


def run_fetch(download_pdfs: bool = True) -> dict:
    cfg = load_config()
    db = DB(DB_PATH)
    fetch_cfg = cfg["fetch"]
    min_score = cfg["relevance"]["min_score"]

    existing = [(fp, t) for fp, t in db.all_norm_titles()]
    new_papers: list[Paper] = []
    stats = {"fetched": 0, "kept": 0, "duplicate": 0, "irrelevant": 0, "by_source": {}}

    for name, src_cfg in cfg["sources"].items():
        if not src_cfg.get("enabled"):
            continue
        fn = REGISTRY.get(name)
        if not fn:
            continue
        console.print(f"[cyan]→ fetching {name}…[/cyan]")
        try:
            results = fn(src_cfg, fetch_cfg)
        except Exception as e:  # noqa: BLE001
            console.print(f"  [red]{name} failed: {e}[/red]")
            continue
        stats["by_source"][name] = len(results)
        stats["fetched"] += len(results)

        for paper in results:
            score_paper(paper, cfg)
            if paper.score < min_score:
                stats["irrelevant"] += 1
                continue
            tag_in_place(paper, cfg)
            if db.exists(paper.fingerprint) or _is_duplicate(paper, existing):
                stats["duplicate"] += 1
                continue
            if db.insert(paper):
                existing.append((paper.fingerprint, paper.title))
                new_papers.append(paper)
                stats["kept"] += 1

    console.print(
        f"\n[bold green]Done.[/bold green] fetched={stats['fetched']} "
        f"kept={stats['kept']} dup={stats['duplicate']} "
        f"irrelevant={stats['irrelevant']}"
    )
    for s, n in stats["by_source"].items():
        console.print(f"  {s}: {n}")

    # Download this run's keepers' PDFs into the library so they can be read
    # during review (status stays pending until accepted).
    if download_pdfs and new_papers:
        from .pdfs import download_for, PDF_LIBRARY
        console.print("\n[cyan]→ downloading candidate PDFs…[/cyan]")
        ps = download_for(new_papers, db)
        stats["pdfs"] = ps
        console.print(
            f"  PDFs: downloaded={ps['downloaded']} failed={ps['failed']} "
            f"no-url={ps['no_url']} → {PDF_LIBRARY}"
        )

    console.print(f"\nPending for review: [bold]{db.counts().get('pending', 0)}[/bold]")
    console.print("Next: [bold]python -m aifinhub review-export[/bold]")
    return stats
