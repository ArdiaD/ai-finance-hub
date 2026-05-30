"""Local PDF archive with a two-stage lifecycle (all local-only, never published).

  pdfs/inbox/<fp>.pdf    temporary — this week's candidates, downloaded at fetch,
                         read during review.
  pdfs/library/<fp>.pdf  permanent — every KEPT paper (your existing backlog plus
                         each week's approved papers).

On approval a PDF is promoted inbox → library; on rejection it's discarded from
the inbox. The public site links to the original pdf_url; these copies are a
private archive on Dropbox.
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
PDF_INBOX = PDF_DIR / "inbox"
PDF_LIBRARY = PDF_DIR / "library"


def inbox_path(fp: str) -> Path:
    return PDF_INBOX / f"{fp}.pdf"


def library_path(fp: str) -> Path:
    return PDF_LIBRARY / f"{fp}.pdf"


def current_path(fp: str) -> Optional[Path]:
    """Wherever this paper's PDF currently lives, if anywhere."""
    for p in (library_path(fp), inbox_path(fp)):
        if p.exists():
            return p
    return None


# ---- download ------------------------------------------------------------
def download_one(pdf_url: str, fingerprint: str, dest_dir: Path = PDF_INBOX) -> Optional[Path]:
    dest = dest_dir / f"{fingerprint}.pdf"
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


def download_for(papers, db: DB, quiet: bool = False) -> dict:
    """Download missing PDFs for the given papers into the inbox."""
    PDF_INBOX.mkdir(parents=True, exist_ok=True)
    stats = {"downloaded": 0, "have": 0, "failed": 0, "no_url": 0}
    for p in papers:
        if current_path(p.fingerprint):
            stats["have"] += 1
            continue
        if not p.pdf_url:
            stats["no_url"] += 1
            continue
        dest = download_one(p.pdf_url, p.fingerprint)
        if dest:
            db.update_fields(p.fingerprint, pdf_path=str(dest))
            stats["downloaded"] += 1
            if not quiet:
                console.print(f"  [green]✓ pdf[/green] {p.title[:58]}")
        else:
            stats["failed"] += 1
            if not quiet:
                console.print(f"  [yellow]✗ pdf (paywalled?) {p.title[:50]}[/yellow]")
    return stats


def download_pdfs(status: str = "pending") -> dict:
    """CLI entry: (re)download PDFs for papers in a status into the inbox."""
    db = DB(DB_PATH)
    papers = db.query(status=None if status == "all" else status)
    stats = download_for(papers, db)
    console.print(
        f"\n[bold]PDFs:[/bold] downloaded={stats['downloaded']} "
        f"already-have={stats['have']} failed={stats['failed']} "
        f"no-url={stats['no_url']}\nInbox: {PDF_INBOX}"
    )
    return stats


# ---- lifecycle transitions ----------------------------------------------
def promote_to_library(fingerprint: str) -> Optional[Path]:
    """Move a kept paper's PDF from inbox (or wherever) into the library."""
    PDF_LIBRARY.mkdir(parents=True, exist_ok=True)
    dest = library_path(fingerprint)
    if dest.exists():
        # already in library; clean up any stray inbox copy
        inbox_path(fingerprint).unlink(missing_ok=True)
        return dest
    src = inbox_path(fingerprint)
    if src.exists():
        shutil.move(str(src), str(dest))
        return dest
    return None


def discard_inbox(fingerprint: str) -> None:
    inbox_path(fingerprint).unlink(missing_ok=True)


# ---- manual attach -------------------------------------------------------
def link_pdf(fingerprint: str, src_path: str) -> None:
    """Attach a manually downloaded PDF (e.g. a paywalled one) to a paper.

    Files it into library if the paper is already approved, else into the inbox.
    """
    db = DB(DB_PATH)
    paper = db.get(fingerprint)
    if not paper:
        raise SystemExit(f"No paper with fingerprint {fingerprint}")
    src = Path(src_path).expanduser()
    if not src.exists():
        raise SystemExit(f"File not found: {src}")
    dest = library_path(fingerprint) if paper.status == "approved" else inbox_path(fingerprint)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    db.update_fields(fingerprint, pdf_path=str(dest))
    console.print(f"[green]Attached[/green] {src.name} → {dest.parent.name}/ "
                  f"({paper.title[:50]})")
