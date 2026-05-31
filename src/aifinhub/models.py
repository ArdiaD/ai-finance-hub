"""Core data model: a normalized Paper record shared by every source."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from typing import Optional


def _norm_title(title: str) -> str:
    """Lowercase, strip punctuation/whitespace — used for dedup fingerprinting."""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


@dataclass
class Paper:
    """A single research paper, normalized across all sources."""

    title: str
    authors: list[str]
    abstract: str
    url: str                       # canonical landing page
    source: str                    # arxiv | repec | ssrn | journal:<name> | scholar
    published: Optional[str] = None  # ISO date string (YYYY-MM-DD) if known
    pdf_url: Optional[str] = None
    pdf_path: Optional[str] = None  # local archived copy (never published)
    categories: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)  # auto-tagged topics
    venue: Optional[str] = None    # journal / working-paper series

    # Pipeline metadata (filled in by the pipeline, not the source)
    score: float = 0.0
    relevance_note: str = ""
    fame_score: Optional[int] = None   # 0-10 relevance to the FAME project
    fame_note: str = ""
    status: str = "pending"        # pending | approved | rejected
    featured: bool = False         # highlighted in the LinkedIn post
    fetched_at: Optional[str] = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.fingerprint:
            self.fingerprint = self.compute_fingerprint()

    def compute_fingerprint(self) -> str:
        """Stable id for dedup: prefer a normalized identifier, else title hash."""
        ident = self._identifier()
        basis = ident if ident else _norm_title(self.title)
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]

    def _identifier(self) -> str:
        """Extract a strong identifier from the URL (arXiv id, DOI, SSRN id)."""
        u = self.url or ""
        if m := re.search(r"arxiv\.org/abs/([\w.\/-]+)", u):
            return "arxiv:" + m.group(1).split("v")[0]
        if m := re.search(r"(10\.\d{4,9}/[^\s\"<>]+)", u):
            return "doi:" + m.group(1).lower().rstrip(".")
        if m := re.search(r"abstract_id=(\d+)", u):
            return "ssrn:" + m.group(1)
        return ""

    @property
    def norm_title(self) -> str:
        return _norm_title(self.title)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Paper":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})
