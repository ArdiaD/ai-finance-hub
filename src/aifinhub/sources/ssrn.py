"""SSRN source — BEST EFFORT.

SSRN has no official public API. This uses the undocumented JSON endpoint that
the SSRN site itself calls. It works today but may break without notice; every
failure is swallowed so it can never take down a run.
"""

from __future__ import annotations

from ..models import Paper
from .base import http_get, cutoff_date

# Undocumented endpoint used by SSRN's own search UI.
SEARCH = "https://api.ssrn.com/content/v1/bindings/204/papers"


def fetch(source_cfg: dict, fetch_cfg: dict) -> list[Paper]:
    cutoff = cutoff_date(fetch_cfg["lookback_days"]).isoformat()
    papers: list[Paper] = []
    for query in source_cfg.get("queries", []):
        try:
            resp = http_get(
                SEARCH,
                params={
                    "term": query,
                    "sort": "0",  # 0 = newest
                    "limit": min(fetch_cfg["max_results_per_source"], 50),
                },
                headers={"Accept": "application/json"},
            )
            data = resp.json()
        except Exception:  # noqa: BLE001 — fragile by design
            continue
        for item in data.get("papers", []):
            pub = (item.get("approved_date") or "")[:10] or None
            if pub and pub < cutoff:
                continue
            aid = item.get("id")
            url = (
                f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={aid}"
                if aid else ""
            )
            authors = [
                a.get("first_name", "") + " " + a.get("last_name", "")
                for a in item.get("authors", [])
            ]
            papers.append(
                Paper(
                    title=" ".join((item.get("title") or "").split()),
                    authors=[a.strip() for a in authors if a.strip()],
                    abstract=" ".join((item.get("abstract") or "").split()),
                    url=url,
                    source="ssrn",
                    published=pub,
                    venue="SSRN working paper",
                )
            )
    return papers
