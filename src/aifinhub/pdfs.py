"""Local PDF archive with a two-stage lifecycle (all local-only, never published).

  pdfs/inbox/<fp>.pdf                 temporary — this week's candidates, downloaded
                                      at fetch, read during review.
  pdfs/library/<surnames>_<year>.pdf  permanent — every KEPT paper (your existing
                                      backlog plus each week's approved papers),
                                      named name1_name2_name3_year.pdf.

On approval a PDF is promoted inbox → library (and renamed to the library
convention); on rejection it's discarded from the inbox. The public site links to
the original pdf_url; these copies are a private archive on Dropbox.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path
from typing import Optional

from rich.console import Console

from .config import ROOT, DB_PATH
from .db import DB
from .models import Paper
from .sources.base import http_get

console = Console()

PDF_DIR = ROOT / "pdfs"
PDF_INBOX = PDF_DIR / "inbox"
PDF_LIBRARY = PDF_DIR / "library"


def inbox_path(fp: str) -> Path:
    return PDF_INBOX / f"{fp}.pdf"


def current_path(fp: str) -> Optional[Path]:
    """An inbox copy if present (library files use human names, see pdf_path)."""
    p = inbox_path(fp)
    return p if p.exists() else None


# ---- library naming: name1_name2_name3_year.pdf --------------------------
def _surname(author: str) -> str:
    toks = author.strip().split()
    if not toks:
        return ""
    s = unicodedata.normalize("NFKD", toks[-1]).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]", "", s)


def _sanitize_stem(stem: str) -> str:
    s = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    s = re.sub(r"\s+", "_", s.strip())
    s = re.sub(r"[^A-Za-z0-9_-]", "", s)
    return s or "paper"


def library_basename(paper: Paper, fallback_stem: Optional[str] = None) -> str:
    """name1_name2_name3_year from up to 3 author surnames + year.

    Falls back to the original PDF filename (already roughly in that format) when
    no authors were resolved, then to the fingerprint.
    """
    surs = [s for s in (_surname(a) for a in paper.authors[:3]) if s]
    year = ""
    if paper.published and paper.published[:4].isdigit():
        year = paper.published[:4]
    if surs:
        base = "_".join(surs)
        return f"{base}_{year}" if year else base
    if fallback_stem:
        return _sanitize_stem(fallback_stem)
    return paper.fingerprint


def unique_library_path(paper: Paper, fallback_stem: Optional[str] = None) -> Path:
    """Library path, disambiguating same surname+year with b/c/d… like 2025b."""
    PDF_LIBRARY.mkdir(parents=True, exist_ok=True)
    base = library_basename(paper, fallback_stem)
    dest = PDF_LIBRARY / f"{base}.pdf"
    if not dest.exists():
        return dest
    for letter in "bcdefghijklmnopqrstuvwxyz":
        cand = PDF_LIBRARY / f"{base}{letter}.pdf"
        if not cand.exists():
            return cand
    return PDF_LIBRARY / f"{base}_{paper.fingerprint[:6]}.pdf"


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
        if (p.pdf_path and Path(p.pdf_path).exists()) or current_path(p.fingerprint):
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
def promote_to_library(paper: Paper, fallback_stem: Optional[str] = None) -> Optional[Path]:
    """Move a kept paper's PDF into the library under the naming convention."""
    if paper.pdf_path:
        cur = Path(paper.pdf_path)
        if cur.exists() and cur.parent == PDF_LIBRARY:
            return cur  # already filed
    src = None
    if paper.pdf_path and Path(paper.pdf_path).exists():
        src = Path(paper.pdf_path)
    elif inbox_path(paper.fingerprint).exists():
        src = inbox_path(paper.fingerprint)
    if not src:
        return None
    dest = unique_library_path(paper, fallback_stem)
    shutil.move(str(src), str(dest))
    return dest


def discard_inbox(fingerprint: str) -> None:
    inbox_path(fingerprint).unlink(missing_ok=True)


def remove_pdf(paper: Paper) -> None:
    """Delete a paper's archived PDF wherever it lives (library or inbox)."""
    if paper.pdf_path:
        Path(paper.pdf_path).unlink(missing_ok=True)
    inbox_path(paper.fingerprint).unlink(missing_ok=True)


def reject_papers(fingerprints: list[str]) -> int:
    """Mark papers rejected and delete their archived PDFs."""
    db = DB(DB_PATH)
    n = 0
    for fp in fingerprints:
        paper = db.get(fp)
        if not paper:
            console.print(f"[yellow]no paper {fp}[/yellow]")
            continue
        remove_pdf(paper)
        db.set_status(fp, "rejected")
        db.update_fields(fp, pdf_path=None)
        console.print(f"[red]rejected[/red] {paper.title[:60]}")
        n += 1
    return n


# ---- manual attach -------------------------------------------------------
def link_pdf(fingerprint: str, src_path: str) -> None:
    """Attach a manually downloaded PDF (e.g. a paywalled one) to a paper.

    Files it into the library (named by convention) if the paper is already
    approved, else into the inbox.
    """
    db = DB(DB_PATH)
    paper = db.get(fingerprint)
    if not paper:
        raise SystemExit(f"No paper with fingerprint {fingerprint}")
    src = Path(src_path).expanduser()
    if not src.exists():
        raise SystemExit(f"File not found: {src}")
    if paper.status == "approved":
        dest = unique_library_path(paper, fallback_stem=src.stem)
    else:
        dest = inbox_path(fingerprint)
        dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    db.update_fields(fingerprint, pdf_path=str(dest))
    console.print(f"[green]Attached[/green] {src.name} → {dest.parent.name}/{dest.name}")
