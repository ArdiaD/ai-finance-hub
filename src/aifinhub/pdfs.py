"""Local PDF archive — download/attach PDFs, kept local-only (never published).

Files live in pdfs/<fingerprint>.pdf (gitignored). The public site links to the
original pdf_url; the local copy is a personal archive on Dropbox.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from rich.console import Console

from .config import ROOT, DB_PATH
from .db import DB
from .sources.base import http_get

console = Console()
PDF_DIR = ROOT / "pdfs"


def _target(fingerprint: str) -> Path:
    return PDF_DIR / f"{fingerprint}.pdf"


def download_one(pdf_url: str, fingerprint: str) -> Optional[Path]:
    dest = _target(fingerprint)
    if dest.exists():
        return dest
    try:
        r = http_get(pdf_url)
        if "pdf" not in r.headers.get("Content-Type", "").lower() and \
                not r.content[:5].startswith(b"%PDF"):
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return dest
    except Exception:  # noqa: BLE001
        return None


def download_pdfs(status: str = "approved") -> dict:
    """Download missing PDFs for papers in the given status (or 'all')."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    db = DB(DB_PATH)
    papers = db.query(status=None if status == "all" else status)
    stats = {"downloaded": 0, "skipped": 0, "failed": 0, "no_url": 0}
    for p in papers:
        if p.pdf_path and Path(p.pdf_path).exists():
            stats["skipped"] += 1
            continue
        if not p.pdf_url:
            stats["no_url"] += 1
            continue
        dest = download_one(p.pdf_url, p.fingerprint)
        if dest:
            db.update_fields(p.fingerprint, pdf_path=str(dest))
            stats["downloaded"] += 1
            console.print(f"  [green]✓[/green] {p.title[:60]}")
        else:
            stats["failed"] += 1
            console.print(f"  [yellow]✗ (paywalled?) {p.title[:55]}[/yellow]")
    console.print(
        f"\n[bold]PDFs:[/bold] downloaded={stats['downloaded']} "
        f"already-have={stats['skipped']} failed={stats['failed']} "
        f"no-url={stats['no_url']}"
    )
    console.print(f"Archive: {PDF_DIR}")
    return stats


def link_pdf(fingerprint: str, src_path: str) -> None:
    """Attach a manually downloaded PDF (e.g. a paywalled one) to a paper."""
    db = DB(DB_PATH)
    paper = db.get(fingerprint)
    if not paper:
        raise SystemExit(f"No paper with fingerprint {fingerprint}")
    src = Path(src_path).expanduser()
    if not src.exists():
        raise SystemExit(f"File not found: {src}")
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    dest = _target(fingerprint)
    shutil.copy2(src, dest)
    db.update_fields(fingerprint, pdf_path=str(dest))
    console.print(f"[green]Attached[/green] {src.name} → {paper.title[:60]}")
