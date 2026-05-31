"""Enrich thin imported papers with LLM-extracted metadata.

Imports of PDFs without an embedded DOI/arXiv id end up "thin" (title is just the
filename, no authors/abstract). This pass reads each such PDF's text with Claude,
extracts title/authors/abstract, re-tags themes, and renames the library file to
the name1_name2_name3_year.pdf convention now that authors are known.

Requires ANTHROPIC_API_KEY. Uses a fast model by default (bulk extraction).
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Optional

from rich.console import Console

from .config import load_config, DB_PATH, env
from .db import DB
from .ingest_pdf import _extract
from .pdfs import PDF_LIBRARY, unique_library_path
from .themes import tag

console = Console()

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _needs_enrichment(p) -> bool:
    return p.source == "manual" and (not p.abstract or not p.authors)


def _llm_extract(text: str, model: str, client) -> Optional[dict]:
    if not text.strip():
        return None
    prompt = (
        "Extract bibliographic metadata from this first page of an academic "
        "paper. Respond with JSON only: "
        '{"title": "", "authors": ["First Last", ...], "abstract": "", "year": ""}. '
        "Authors in reading order. If a field is unknown use an empty string / "
        "empty list.\n\n" + text[:5000]
    )
    try:
        msg = client.messages.create(
            model=model, max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text
        raw = raw[raw.find("{"): raw.rfind("}") + 1]
        return json.loads(raw)
    except Exception as e:  # noqa: BLE001
        console.print(f"    [red]LLM error: {e}[/red]")
        return None


def enrich(limit: Optional[int] = None, model: str = DEFAULT_MODEL,
           status: str = "all") -> dict:
    if not env("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set (add it to .env).")
    try:
        import anthropic
    except ImportError:
        raise SystemExit("pip install anthropic")

    cfg = load_config()
    db = DB(DB_PATH)
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))

    rows = db.query(status=None if status == "all" else status)
    targets = [p for p in rows if _needs_enrichment(p)]
    if limit:
        targets = targets[:limit]
    console.print(f"Enriching [bold]{len(targets)}[/bold] thin papers with {model}\n")

    stats = {"enriched": 0, "renamed": 0, "no_pdf": 0, "failed": 0}
    for p in targets:
        if not p.pdf_path or not Path(p.pdf_path).exists():
            stats["no_pdf"] += 1
            continue
        text, _ = _extract(Path(p.pdf_path), max_pages=3)
        data = _llm_extract(text, model, client)
        if not data or not data.get("title"):
            stats["failed"] += 1
            console.print(f"  [yellow]· {Path(p.pdf_path).name} (no extract)[/yellow]")
            continue

        title = " ".join(str(data["title"]).split()) or p.title
        authors = [a for a in data.get("authors", []) if a] or p.authors
        abstract = " ".join(str(data.get("abstract", "")).split()) or p.abstract

        # Year: prefer LLM, else parse from the current filename, else keep.
        published = p.published
        yr = str(data.get("year", "")).strip()
        if not yr:
            m = YEAR_RE.search(Path(p.pdf_path).stem)
            yr = m.group(0) if m else ""
        if yr and len(yr) == 4 and yr.isdigit():
            published = f"{yr}-01-01"

        db.update_fields(
            p.fingerprint, title=title, authors=json.dumps(authors),
            abstract=abstract, published=published,
        )
        updated = db.get(p.fingerprint)
        db.update_fields(p.fingerprint, themes=json.dumps(tag(updated, cfg)))
        updated = db.get(p.fingerprint)
        stats["enriched"] += 1

        # Rename the library file now that we have authors.
        if p.status == "approved" and p.pdf_path:
            old = Path(p.pdf_path)
            new = unique_library_path(updated, fallback_stem=old.stem)
            if old.resolve() != new.resolve():
                shutil.move(str(old), str(new))
                db.update_fields(p.fingerprint, pdf_path=str(new))
                stats["renamed"] += 1
        console.print(f"  [green]✓[/green] {title[:55]}  ({len(authors)} authors)")

    console.print(
        f"\n[bold green]Enriched {stats['enriched']}[/bold green] "
        f"(renamed {stats['renamed']}) · no-pdf={stats['no_pdf']} "
        f"failed={stats['failed']}"
    )
    return stats
