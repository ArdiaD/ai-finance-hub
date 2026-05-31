"""OpenAlex venue source — targeted AI-in-finance papers from curated journals.

Two batched queries (reliable, free, no key, abstracts included):
  * finance/quant journals  searched for AI terms      (AI methods in finance)
  * ML/AI journals          searched for finance terms (finance applications)

Each result still passes the AI×finance relevance gate downstream, so the venue
searches just pre-filter to a sane volume. Far more stable than scraping RSS.
"""

from __future__ import annotations

import html

from ..config import env
from ..models import Paper
from .base import http_get, cutoff_date

API = "https://api.openalex.org/works"
SELECT = "title,authorships,abstract_inverted_index,doi,publication_date,primary_location"


def _abstract(inv: dict) -> str:
    """Reconstruct plain text from OpenAlex's abstract_inverted_index."""
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def _query(ids, search, fetch_cfg) -> list[Paper]:
    if not ids or not search:
        return []
    cutoff = cutoff_date(fetch_cfg["lookback_days"]).isoformat()
    flt = (f"primary_location.source.id:{'|'.join(ids)},"
           f"from_publication_date:{cutoff},"
           f"title_and_abstract.search:{search}")
    params = {
        "filter": flt, "select": SELECT, "sort": "publication_date:desc",
        "per-page": min(fetch_cfg["max_results_per_source"], 100),
        "mailto": env("CROSSREF_MAILTO") or "research@example.com",
    }
    data = http_get(API, params=params).json().get("results", [])
    papers = []
    for w in data:
        src = (w.get("primary_location") or {}).get("source") or {}
        doi = w.get("doi") or ""
        url = doi if doi.startswith("http") else (f"https://doi.org/{doi}" if doi else "")
        papers.append(Paper(
            title=html.unescape(" ".join((w.get("title") or "").split())),
            authors=[a["author"]["display_name"] for a in w.get("authorships", [])
                     if a.get("author")],
            abstract=html.unescape(_abstract(w.get("abstract_inverted_index"))),
            url=url, source="journal", venue=src.get("display_name"),
            published=w.get("publication_date"),
        ))
    return papers


def fetch(source_cfg: dict, fetch_cfg: dict) -> list[Paper]:
    papers: list[Paper] = []
    try:  # finance/quant venues → search for AI methods
        papers += _query(list(source_cfg.get("finance_venues", {}).values()),
                         source_cfg.get("ai_search", ""), fetch_cfg)
    except Exception:  # noqa: BLE001
        pass
    try:  # ML/AI venues → search for finance applications
        papers += _query(list(source_cfg.get("ai_venues", {}).values()),
                         source_cfg.get("finance_search", ""), fetch_cfg)
    except Exception:  # noqa: BLE001
        pass
    return papers
