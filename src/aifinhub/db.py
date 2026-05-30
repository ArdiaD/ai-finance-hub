"""SQLite storage for the paper pipeline.

The DB is the working source of truth (dedup, status, fetch log). The curated
*approved* corpus is also exported to docs/papers.json for the public site.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from .models import Paper

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    fingerprint   TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    authors       TEXT NOT NULL,   -- JSON array
    abstract      TEXT,
    url           TEXT,
    pdf_url       TEXT,
    source        TEXT,
    venue         TEXT,
    categories    TEXT,            -- JSON array
    published     TEXT,
    score         REAL DEFAULT 0,
    relevance_note TEXT DEFAULT '',
    status        TEXT DEFAULT 'pending',
    featured      INTEGER DEFAULT 0,
    fetched_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_status ON papers(status);
CREATE INDEX IF NOT EXISTS idx_fetched ON papers(fetched_at);
"""


class DB:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- writes -----------------------------------------------------------
    def exists(self, fingerprint: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM papers WHERE fingerprint = ?", (fingerprint,)
        )
        return cur.fetchone() is not None

    def insert(self, p: Paper) -> bool:
        """Insert a paper. Returns False if it already existed (deduped)."""
        if self.exists(p.fingerprint):
            return False
        p.fetched_at = p.fetched_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.conn.execute(
            """INSERT INTO papers
               (fingerprint, title, authors, abstract, url, pdf_url, source,
                venue, categories, published, score, relevance_note, status,
                featured, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                p.fingerprint, p.title, json.dumps(p.authors), p.abstract, p.url,
                p.pdf_url, p.source, p.venue, json.dumps(p.categories), p.published,
                p.score, p.relevance_note, p.status, int(p.featured), p.fetched_at,
            ),
        )
        self.conn.commit()
        return True

    def set_status(self, fingerprint: str, status: str, featured: Optional[bool] = None) -> None:
        if featured is None:
            self.conn.execute(
                "UPDATE papers SET status=? WHERE fingerprint=?", (status, fingerprint)
            )
        else:
            self.conn.execute(
                "UPDATE papers SET status=?, featured=? WHERE fingerprint=?",
                (status, int(featured), fingerprint),
            )
        self.conn.commit()

    def update_fields(self, fingerprint: str, **fields) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(
            f"UPDATE papers SET {cols} WHERE fingerprint=?",
            (*fields.values(), fingerprint),
        )
        self.conn.commit()

    # ---- reads ------------------------------------------------------------
    def _row_to_paper(self, r: sqlite3.Row) -> Paper:
        return Paper(
            title=r["title"], authors=json.loads(r["authors"]),
            abstract=r["abstract"] or "", url=r["url"] or "", source=r["source"] or "",
            published=r["published"], pdf_url=r["pdf_url"],
            categories=json.loads(r["categories"] or "[]"), venue=r["venue"],
            score=r["score"], relevance_note=r["relevance_note"] or "",
            status=r["status"], featured=bool(r["featured"]),
            fetched_at=r["fetched_at"], fingerprint=r["fingerprint"],
        )

    def query(self, status: Optional[str] = None, order: str = "score DESC") -> list[Paper]:
        sql = "SELECT * FROM papers"
        params: tuple = ()
        if status:
            sql += " WHERE status = ?"
            params = (status,)
        sql += f" ORDER BY {order}"
        return [self._row_to_paper(r) for r in self.conn.execute(sql, params)]

    def get(self, fingerprint: str) -> Optional[Paper]:
        r = self.conn.execute(
            "SELECT * FROM papers WHERE fingerprint=?", (fingerprint,)
        ).fetchone()
        return self._row_to_paper(r) if r else None

    def all_norm_titles(self) -> list[tuple[str, str]]:
        """(fingerprint, normalized_title) for fuzzy dedup."""
        return [
            (r["fingerprint"], r["title"])
            for r in self.conn.execute("SELECT fingerprint, title FROM papers")
        ]

    def counts(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) c FROM papers GROUP BY status"
        )
        return {r["status"]: r["c"] for r in rows}
