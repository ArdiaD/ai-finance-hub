"""arXiv source — the reliable backbone. Uses the official Atom API."""

from __future__ import annotations

import feedparser

from ..models import Paper
from .base import http_get, cutoff_date, parse_date

API = "http://export.arxiv.org/api/query"


def fetch(source_cfg: dict, fetch_cfg: dict) -> list[Paper]:
    cats = source_cfg.get("categories", [])
    if not cats:
        return []
    search = " OR ".join(f"cat:{c}" for c in cats)
    params = {
        "search_query": search,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": fetch_cfg["max_results_per_source"],
    }
    resp = http_get(API, params=params)
    feed = feedparser.parse(resp.text)
    cutoff = cutoff_date(fetch_cfg["lookback_days"])

    papers: list[Paper] = []
    for e in feed.entries:
        published = parse_date(e.get("published_parsed"))
        if published and published < cutoff.isoformat():
            continue
        pdf = next(
            (l.href for l in e.get("links", []) if l.get("type") == "application/pdf"),
            None,
        )
        papers.append(
            Paper(
                title=" ".join(e.title.split()),
                authors=[a.name for a in e.get("authors", [])],
                abstract=" ".join(e.get("summary", "").split()),
                url=e.get("link", ""),
                pdf_url=pdf,
                source="arxiv",
                published=published,
                categories=[t.term for t in e.get("tags", [])],
                venue="arXiv preprint",
            )
        )
    return papers
