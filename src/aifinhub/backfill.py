"""Backfill URL / venue / DOI for papers that lack them (mainly manual imports).

Queries Crossref (published works) and arXiv (preprints) by title, then accepts a
match only when the returned title is a close fuzzy match — so we never attach a
wrong link. Safe to re-run; only fills empty fields.
"""

from __future__ import annotations

import re
import time
from typing import Optional

import feedparser
import requests
from rapidfuzz import fuzz
from rich.console import Console

from .config import DB_PATH, env
from .db import DB
from .metadata import _clean
from .sources.base import http_get, UA

console = Console()

ACCEPT = 90          # min title similarity to accept any match
STRICT = 95          # at/above this, accept on title alone
SURNAME_MIN = 88     # between ACCEPT and STRICT, also require a first-author match


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _surname(author: str) -> str:
    toks = (author or "").split()
    return toks[-1].lower() if toks else ""


def _crossref(title: str) -> list[dict]:
    mailto = env("CROSSREF_MAILTO") or "research@example.com"
    try:
        r = http_get("https://api.crossref.org/works",
                     params={"query.bibliographic": title, "rows": 5, "mailto": mailto},
                     timeout=15)
        items = r.json()["message"]["items"]
    except Exception:  # noqa: BLE001
        return []
    out = []
    for m in items:
        t = (m.get("title") or [""])[0]
        if not t:
            continue
        out.append({
            "title": _clean(t),
            "url": m.get("URL") or (f"https://doi.org/{m['DOI']}" if m.get("DOI") else ""),
            "venue": (m.get("container-title") or [None])[0],
            "pdf_url": None,
            "authors": [a.get("family", "") for a in m.get("author", [])],
        })
    return out


def _arxiv(title: str) -> list[dict]:
    try:
        r = http_get("http://export.arxiv.org/api/query",
                     params={"search_query": f'ti:"{title}"', "max_results": 5},
                     timeout=15)
        feed = feedparser.parse(r.text)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for e in feed.entries:
        pdf = next((l.href for l in e.get("links", [])
                    if l.get("type") == "application/pdf"), None)
        out.append({
            "title": _clean(e.get("title", "")),
            "url": e.get("link", ""),
            "venue": "arXiv preprint",
            "pdf_url": pdf,
            "authors": [a.name for a in e.get("authors", [])],
        })
    return out


def _semanticscholar(title: str, tries: int = 4) -> list[dict]:
    """Semantic Scholar covers arXiv + published with stable external ids.

    The unauthenticated endpoint rate-limits bursts (429), so retry with backoff.
    """
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {"query": title, "limit": 5,
              "fields": "title,externalIds,url,venue,openAccessPdf,authors"}
    headers = {"User-Agent": UA}
    key = env("SEMANTIC_SCHOLAR_KEY")  # optional free key removes rate limits
    if key:
        headers["x-api-key"] = key
    data = []
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=20)
        except Exception:  # noqa: BLE001
            return []
        if r.status_code == 429:
            time.sleep(4 * (attempt + 1))  # 4, 8, 12, 16s backoff
            continue
        if r.status_code != 200:
            return []
        data = r.json().get("data", [])
        break
    out = []
    for m in data:
        ext = m.get("externalIds") or {}
        if ext.get("ArXiv"):
            url = f"https://arxiv.org/abs/{ext['ArXiv']}"
        elif ext.get("DOI"):
            url = f"https://doi.org/{ext['DOI']}"
        else:
            url = (m.get("openAccessPdf") or {}).get("url") or m.get("url") or ""
        out.append({
            "title": _clean(m.get("title", "")),
            "url": url,
            "venue": m.get("venue") or None,
            "pdf_url": (m.get("openAccessPdf") or {}).get("url"),
            "authors": [a.get("name", "") for a in m.get("authors", [])],
        })
    return out


def _best(paper, cands: list[dict]) -> Optional[dict]:
    nt = _norm(paper.title)
    first_sur = _surname(paper.authors[0]) if paper.authors else ""
    best, best_r = None, 0
    for c in cands:
        if not c.get("url"):
            continue
        r = fuzz.token_sort_ratio(nt, _norm(c["title"]))
        if r > best_r:
            best, best_r = c, r
    if not best or best_r < ACCEPT:
        return None
    if best_r < STRICT and first_sur:
        cand_sur = " ".join(_surname(a) for a in best.get("authors", []))
        if first_sur not in cand_sur and best_r < SURNAME_MIN + 4:
            return None
    return best


def _origin(url: str):
    """Map a paper URL to (source, default_venue) for accurate provenance."""
    if not url:
        return None
    if "arxiv.org" in url:
        return ("arxiv", "arXiv preprint")
    if "10.2139/ssrn" in url or "ssrn.com" in url:
        return ("ssrn", "SSRN")
    if "doi.org" in url:
        return ("journal", None)  # venue (journal name) usually already set
    return None


def relabel_sources() -> dict:
    """Replace 'manual' source with the real origin (arXiv/SSRN/journal) by URL.

    Imported papers all carry source='manual' (how they entered); this rewrites
    that to where the paper actually lives, so cards/filters read correctly.
    """
    db = DB(DB_PATH)
    manual = [p for p in db.query() if p.source == "manual"]
    counts: dict[str, int] = {}
    for p in manual:
        o = _origin(p.url)
        if not o:
            continue
        src, ven = o
        fields = {"source": src}
        if ven and not p.venue:
            fields["venue"] = ven
        db.update_fields(p.fingerprint, **fields)
        counts[src] = counts.get(src, 0) + 1
    left = len([p for p in db.query() if p.source == "manual"])
    console.print(f"[green]Relabeled:[/green] " +
                  " ".join(f"{k}={v}" for k, v in counts.items()) +
                  f" · still 'manual' (no URL): {left}")
    return counts


def backfill_urls(limit: Optional[int] = None) -> dict:
    db = DB(DB_PATH)
    targets = [p for p in db.query() if not p.url]
    if limit:
        targets = targets[:limit]
    console.print(f"Backfilling URLs for [bold]{len(targets)}[/bold] papers "
                  "(Crossref + arXiv)…\n")
    stats = {"matched": 0, "unmatched": 0}
    unmatched = []
    for p in targets:
        # Semantic Scholar first (covers arXiv + published, stable ids); fall back
        # to Crossref/arXiv only if it doesn't yield a confident match.
        best = _best(p, _semanticscholar(p.title))
        if not best:
            best = _best(p, _crossref(p.title) + _arxiv(p.title))
        time.sleep(3)  # politeness — Semantic Scholar's free tier 429s on bursts
        if not best:
            stats["unmatched"] += 1
            unmatched.append(p)
            continue
        fields = {"url": best["url"]}
        if best.get("venue") and not p.venue:
            fields["venue"] = best["venue"]
        if best.get("pdf_url") and not p.pdf_url:
            fields["pdf_url"] = best["pdf_url"]
        db.update_fields(p.fingerprint, **fields)
        stats["matched"] += 1
        console.print(f"  [green]✓[/green] {p.title[:48]}  →  {best['url']}")

    console.print(
        f"\n[bold green]Matched {stats['matched']}[/bold green] · "
        f"unmatched {stats['unmatched']}"
    )
    if unmatched:
        console.print("\n[yellow]No confident match (left as-is):[/yellow]")
        for p in unmatched[:40]:
            console.print(f"  · {p.title[:70]}")
    return stats
