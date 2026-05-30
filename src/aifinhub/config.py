"""Configuration loading and small env helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config.yaml"
DB_PATH = ROOT / "hub.db"
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
        os.environ.setdefault(key.strip(), val.strip())


def load_config() -> dict[str, Any]:
    _load_dotenv()
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def env(name: str, default: str = "") -> str:
    _load_dotenv()
    return os.environ.get(name, default)
