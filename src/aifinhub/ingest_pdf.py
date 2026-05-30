"""Import a folder of existing PDFs into the database.

For each PDF: extract first-page text, find a DOI/arXiv id, and resolve clean
metadata from Crossref/arXiv. Fall back to LLM extraction (if ANTHROPIC_API_KEY)
then to the PDF's own title / filename. Imported papers bypass the relevance gate
(they're hand-picked) and default to 'pending' so they flow through Excel review.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from pypdf import PdfReader
from rapidfuzz import fuzz
from rich.console import Console

from .config import DB_PATH, env, load_config
from .db import DB
from .metadata import find_identifiers, resolve
from .models import Paper
from .pdfs import PDF_DIR

console = Console()
FUZZY_THRESHOLD = 92


def _extract(path: Path, max_pages: int = 2) -> tuple[str, Optional[str]]:
    """Return (first-pages text, embedded PDF title)."""
    try:
        reader = PdfReader(str(path))
        meta_title = reader.metadata.title if reader.metadata else None
        text = "\n".join((reader.pages[i].extract_text() or "")
                         for i in range(min(max_pages, len(reader.pages))))
        return text, (meta_title or None)
    except Exception:  # noqa: BLE001
        return "", None


def _llm_extract(text: str, cfg: dict) -> Optional[dict]:
    if not env("ANTHROPIC_API_KEY") or not text.strip():
        return None
    try:
        import anthropic
    except ImportError:
        return None
    prompt = (
        "Extract bibliographic metadata from this first page of an academic "
        "paper. Respond with JSON only: "
        '{"title": "", "authors": ["First Last", ...], "abstract": ""}. '
        "If a field is unknown use an empty string / empty list.\n\n" + text[:4000]
    )
    try:
        client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model=cfg["relevance"]["llm_model"], max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text
        raw = raw[raw.find("{"): raw.rfind("}") + 1]
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return None


def _is_dup(paper: Paper, db: DB) -> bool:
    if db.exists(paper.fingerprint):
        return True
    nt = paper.norm_title
    if len(nt) < 8:
        return False
    return any(fuzz.token_sort_ratio(nt, t.lower()) >= FUZZY_THRESHOLD
               for _, t in db.all_norm_titles())


def import_pdfs(folder: str, status: str = "pending") -> dict:
    cfg = load_config()
    db = DB(DB_PATH)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    root = Path(folder).expanduser()
    pdf_files = sorted(root.rglob("*.pdf"))
    if not pdf_files:
        console.print(f"[yellow]No PDFs found under {root}[/yellow]")
        return {}

    console.print(f"Importing [bold]{len(pdf_files)}[/bold] PDFs from {root}\n")
    stats = {"imported": 0, "duplicate": 0, "unreadable": 0,
             "via_id": 0, "via_llm": 0, "via_filename": 0}

    for pf in pdf_files:
        text, meta_title = _extract(pf)
        ids = find_identifiers(text)
        meta = resolve(ids) if ids else None
        if meta and meta.get("title"):
            stats["via_id"] += 1
        else:
            llm = _llm_extract(text, cfg)
            if llm and llm.get("title"):
                meta = {"title": llm["title"], "authors": llm.get("authors", []),
                        "abstract": llm.get("abstract", ""), "url": "",
                        "venue": None, "published": None}
                stats["via_llm"] += 1
            else:
                title = (meta_title or pf.stem.replace("_", " ")).strip()
                meta = {"title": title, "authors": [], "abstract": "",
                        "url": "", "venue": None, "published": None}
                stats["via_filename"] += 1

        paper = Paper(
            title=meta["title"], authors=meta.get("authors", []),
            abstract=meta.get("abstract", ""), url=meta.get("url", "") or "",
            source="manual", venue=meta.get("venue"),
            published=meta.get("published"), pdf_url=meta.get("pdf_url"),
            categories=meta.get("categories", []),
            score=99.0, relevance_note="manual PDF import", status=status,
        )

        if _is_dup(paper, db):
            stats["duplicate"] += 1
            console.print(f"  [dim]dup:[/dim] {paper.title[:60]}")
            continue

        # Archive the PDF under the fingerprint and record the local path.
        dest = PDF_DIR / f"{paper.fingerprint}.pdf"
        if not dest.exists():
            shutil.copy2(pf, dest)
        paper.pdf_path = str(dest)
        db.insert(paper)
        stats["imported"] += 1
        console.print(f"  [green]✓[/green] {paper.title[:60]}")

    console.print(
        f"\n[bold green]Imported {stats['imported']}[/bold green] "
        f"(by id={stats['via_id']}, by LLM={stats['via_llm']}, "
        f"by filename={stats['via_filename']}) · duplicates={stats['duplicate']}"
    )
    console.print(f"Status: [bold]{status}[/bold]. Next: "
                  "[bold]python -m aifinhub review-export[/bold]")
    return stats
