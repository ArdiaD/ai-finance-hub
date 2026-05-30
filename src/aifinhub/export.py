"""Export approved papers to docs/papers.json and (re)generate the site."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from rich.console import Console

from .config import load_config, DB_PATH, DOCS_DIR
from .db import DB
from .site import render_index

console = Console()


def build_site() -> None:
    cfg = load_config()
    db = DB(DB_PATH)
    approved = db.query(status="approved", order="published DESC, fetched_at DESC")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "count": len(approved),
        "hub": cfg["hub"],
        "papers": [
            {
                "title": p.title, "authors": p.authors, "abstract": p.abstract,
                "url": p.url, "pdf_url": p.pdf_url, "source": p.source,
                "venue": p.venue, "categories": p.categories,
                "published": p.published, "featured": p.featured,
                "fingerprint": p.fingerprint,
            }
            for p in approved
        ],
    }
    (DOCS_DIR / "papers.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    render_index(cfg, DOCS_DIR)

    console.print(
        f"[green]Wrote {len(approved)} papers → docs/papers.json[/green]\n"
        "Commit & push docs/ to publish on GitHub Pages."
    )
