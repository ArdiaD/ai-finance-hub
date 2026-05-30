"""Journal table-of-contents source via publisher RSS/Atom feeds.

These surface *published* (peer-reviewed) work. Feed URLs occasionally change
when publishers redesign; a dead feed is skipped, not fatal.
"""

from __future__ import annotations

import feedparser

from ..models import Paper
from .base import http_get, cutoff_date, parse_date


def fetch(source_cfg: dict, fetch_cfg: dict) -> list[Paper]:
    cutoff = cutoff_date(fetch_cfg["lookback_days"]).isoformat()
    papers: list[Paper] = []
    for name, url in source_cfg.get("feeds", {}).items():
        try:
            resp = http_get(url)
        except Exception:  # noqa: BLE001
            continue
        feed = feedparser.parse(resp.text)
        for e in feed.entries[: fetch_cfg["max_results_per_source"]]:
            published = parse_date(e.get("published_parsed")) or parse_date(
                e.get("updated_parsed")
            )
            if published and published < cutoff:
                continue
            authors = []
            if "authors" in e:
                authors = [a.get("name", "") for a in e.authors if a.get("name")]
            elif e.get("author"):
                authors = [e.author]
            # Many feeds put the abstract in summary or content.
            abstract = e.get("summary", "")
            if not abstract and e.get("content"):
                abstract = e.content[0].get("value", "")
            papers.append(
                Paper(
                    title=" ".join(e.get("title", "").split()),
                    authors=authors,
                    abstract=" ".join(abstract.split()),
                    url=e.get("link", ""),
                    source=f"journal:{name}",
                    published=published,
                    venue=name,
                )
            )
    return papers
