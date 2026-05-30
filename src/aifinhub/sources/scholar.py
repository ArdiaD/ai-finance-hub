"""Google Scholar source — BEST EFFORT.

Google Scholar has no API and blocks scrapers aggressively. Two backends:
  * serpapi   — reliable, needs SERPAPI_KEY (free tier available).
  * scholarly — free library, frequently rate-limited / CAPTCHA-blocked.
Disabled by default in config.yaml.
"""

from __future__ import annotations

from ..config import env
from ..models import Paper


def fetch(source_cfg: dict, fetch_cfg: dict) -> list[Paper]:
    backend = source_cfg.get("backend", "serpapi")
    if backend == "serpapi":
        return _serpapi(source_cfg, fetch_cfg)
    return _scholarly(source_cfg, fetch_cfg)


def _serpapi(source_cfg: dict, fetch_cfg: dict) -> list[Paper]:
    key = env("SERPAPI_KEY")
    if not key:
        return []
    try:
        from serpapi import GoogleSearch  # type: ignore
    except ImportError:
        return []

    papers: list[Paper] = []
    for query in source_cfg.get("queries", []):
        try:
            results = GoogleSearch(
                {"engine": "google_scholar", "q": query, "api_key": key,
                 "scisbd": 1}  # sort by date
            ).get_dict()
        except Exception:  # noqa: BLE001
            continue
        for r in results.get("organic_results", []):
            pub = r.get("publication_info", {})
            papers.append(
                Paper(
                    title=" ".join((r.get("title") or "").split()),
                    authors=[a.get("name", "") for a in pub.get("authors", [])],
                    abstract=" ".join((r.get("snippet") or "").split()),
                    url=r.get("link", ""),
                    source="scholar",
                    venue=pub.get("summary", ""),
                )
            )
    return papers


def _scholarly(source_cfg: dict, fetch_cfg: dict) -> list[Paper]:
    try:
        from scholarly import scholarly  # type: ignore
    except ImportError:
        return []
    papers: list[Paper] = []
    limit = min(fetch_cfg["max_results_per_source"], 20)
    for query in source_cfg.get("queries", []):
        try:
            search = scholarly.search_pubs(query)
            for _ in range(limit):
                r = next(search, None)
                if r is None:
                    break
                bib = r.get("bib", {})
                papers.append(
                    Paper(
                        title=" ".join((bib.get("title") or "").split()),
                        authors=bib.get("author", []) if isinstance(bib.get("author"), list)
                        else [bib.get("author", "")],
                        abstract=" ".join((bib.get("abstract") or "").split()),
                        url=r.get("pub_url", ""),
                        source="scholar",
                        published=str(bib.get("pub_year", "")) or None,
                        venue=bib.get("venue", ""),
                    )
                )
        except Exception:  # noqa: BLE001
            continue
    return papers
