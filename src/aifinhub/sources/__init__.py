"""Source plugins. Each exposes `fetch(source_cfg, fetch_cfg) -> list[Paper]`."""

from . import arxiv, repec, ssrn, journals, scholar

REGISTRY = {
    "arxiv": arxiv.fetch,
    "repec": repec.fetch,
    "ssrn": ssrn.fetch,
    "journals": journals.fetch,
    "scholar": scholar.fetch,
}
