"""Resolve clean paper metadata from a DOI or arXiv id via free public APIs.

Used when importing local PDFs: we'd rather pull authoritative title/authors/
abstract from Crossref or arXiv than scrape them out of the PDF text.
"""

from __future__ import annotations

import re
from typing import Optional

import feedparser

from .config import env
from .sources.base import http_get

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.I)
ARXIV_RE = re.compile(r"arxiv:\s*(\d{4}\.\d{4,5})(v\d+)?", re.I)


def find_identifiers(text: str) -> dict:
    """Pull the first DOI and/or arXiv id out of extracted PDF text."""
    out: dict = {}
    if m := ARXIV_RE.search(text):
        out["arxiv"] = m.group(1)
    if m := DOI_RE.search(text):
        out["doi"] = m.group(0).rstrip(".,;)")
    return out


def _clean(s: str) -> str:
    return " ".join((s or "").split())


def resolve_doi(doi: str) -> Optional[dict]:
    mailto = env("CROSSREF_MAILTO") or "research@example.com"
    try:
        r = http_get(f"https://api.crossref.org/works/{doi}",
                     params={"mailto": mailto}, timeout=15)
        m = r.json()["message"]
    except Exception:  # noqa: BLE001
        return None
    authors = [
        _clean(f"{a.get('given', '')} {a.get('family', '')}")
        for a in m.get("author", [])
    ]
    parts = (m.get("issued", {}).get("date-parts") or [[None]])[0]
    published = "-".join(f"{p:02d}" if i else str(p) for i, p in enumerate(parts)) \
        if parts and parts[0] else None
    abstract = re.sub(r"<[^>]+>", "", m.get("abstract", "") or "")  # strip JATS tags
    title = (m.get("title") or [""])[0]
    return {
        "title": _clean(title),
        "authors": [a for a in authors if a],
        "abstract": _clean(abstract),
        "published": published,
        "venue": (m.get("container-title") or [None])[0],
        "url": m.get("URL", f"https://doi.org/{doi}"),
    }


def resolve_arxiv(aid: str) -> Optional[dict]:
    try:
        r = http_get("http://export.arxiv.org/api/query",
                     params={"id_list": aid}, timeout=15)
        feed = feedparser.parse(r.text)
        if not feed.entries:
            return None
        e = feed.entries[0]
    except Exception:  # noqa: BLE001
        return None
    pdf = next((l.href for l in e.get("links", [])
                if l.get("type") == "application/pdf"), None)
    return {
        "title": _clean(e.title),
        "authors": [a.name for a in e.get("authors", [])],
        "abstract": _clean(e.get("summary", "")),
        "published": (e.get("published", "") or "")[:10] or None,
        "venue": "arXiv preprint",
        "url": e.get("link", ""),
        "pdf_url": pdf,
        "categories": [t.term for t in e.get("tags", [])],
    }


def resolve(identifiers: dict) -> Optional[dict]:
    """Prefer arXiv (richer abstract) then DOI."""
    if "arxiv" in identifiers:
        if meta := resolve_arxiv(identifiers["arxiv"]):
            return meta
    if "doi" in identifiers:
        return resolve_doi(identifiers["doi"])
    return None
