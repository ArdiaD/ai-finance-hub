"""Configuration loading and small env helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config.yaml"

# All working data lives under data/ (gitignored); code/config/docs stay at root.
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "hub.db"
INCOMING_DIR = DATA_DIR / "pdfs" / "incoming"   # drop PDFs here to import
PDF_CANDIDATES_DIR = DATA_DIR / "pdfs" / "candidates"  # fetched, awaiting review
PDF_LIBRARY_DIR = DATA_DIR / "pdfs" / "library"  # curated/kept PDFs
EXCEL_REVIEW_DIR = DATA_DIR / "excel" / "review"  # review spreadsheets
EXCEL_CORPUS_DIR = DATA_DIR / "excel" / "corpus"  # corpus exports

DOCS_DIR = ROOT / "docs"
OUT_DIR = ROOT / "out"


def _load_dotenv() -> None:
    """Minimal .env loader (avoids a hard python-dotenv dependency)."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        # Fill in vars that are unset OR present-but-empty (some shells export
        # empty placeholders); never clobber a real exported value.
        if val and not os.environ.get(key):
            os.environ[key] = val


def load_config() -> dict[str, Any]:
    _load_dotenv()
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def env(name: str, default: str = "") -> str:
    _load_dotenv()
    return os.environ.get(name, default)
