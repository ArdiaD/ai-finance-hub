"""RePEc source via NEP (New Economics Papers) report RSS feeds.

Each NEP report is an editor-curated weekly list. The feeds are public RSS and
quite stable, making this a reliable secondary backbone alongside arXiv.
"""

from __future__ import annotations

import feedparser

from ..models import Paper
from .base import http_get, parse_date

# NEP reports are published as RSS at this pattern (note the .rss.xml suffix).
FEED = "https://nep.repec.org/rss/{code}.rss.xml"


def fetch(source_cfg: dict, fetch_cfg: dict) -> list[Paper]:
    # NOTE: NEP items carry the *working paper's* date (often weeks old), not the
    # date they entered the report, so we do NOT apply the lookback cutoff here.
    # Each NEP report is an editor-curated weekly digest; week-over-week repeats
    # are handled by fingerprint/fuzzy dedup in the fetch orchestrator.
    papers: list[Paper] = []
    for code in source_cfg.get("nep_reports", []):
        try:
            resp = http_get(FEED.format(code=code))
        except Exception:  # noqa: BLE001 — skip a dead feed, keep the run alive
            continue
        feed = feedparser.parse(resp.text)
        for e in feed.entries[: fetch_cfg["max_results_per_source"]]:
            published = parse_date(e.get("published_parsed")) or parse_date(
                e.get("updated_parsed")
            )
            # feedparser exposes multiple authors in e.authors; fall back to the
            # single author string WITHOUT comma-splitting ("Last, First" would
            # otherwise be mangled into two people).
            if e.get("authors"):
                author_list = [a.get("name", "").strip() for a in e.authors if a.get("name")]
            else:
                author_list = [s.strip() for s in e.get("author", "").split(";") if s.strip()]
            papers.append(
                Paper(
                    title=" ".join(e.get("title", "").split()),
                    authors=author_list,
                    abstract=" ".join(e.get("summary", "").split()),
                    url=e.get("link", ""),
                    source="repec",
                    published=published,
                    venue=f"RePEc/{code}",
                    categories=[code],
                )
            )
    return papers
