"""Shared helpers for source plugins."""

from __future__ import annotations

import datetime as _dt
from typing import Optional

import requests

UA = "ai-finance-hub/0.1 (+https://github.com/ArdiaD/ai-finance-hub)"
TIMEOUT = 30


def http_get(url: str, **kwargs) -> requests.Response:
    headers = {"User-Agent": UA, **kwargs.pop("headers", {})}
    timeout = kwargs.pop("timeout", TIMEOUT)
    r = requests.get(url, headers=headers, timeout=timeout, **kwargs)
    r.raise_for_status()
    return r


def cutoff_date(lookback_days: int) -> _dt.date:
    return _dt.date.today() - _dt.timedelta(days=lookback_days)


def parse_date(value) -> Optional[str]:
    """Coerce assorted date inputs into an ISO YYYY-MM-DD string."""
    if value is None:
        return None
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, (tuple, _dt.struct_time)) if hasattr(_dt, "struct_time") else False:
        pass
    try:
        # feedparser time.struct_time
        import time
        if isinstance(value, time.struct_time):
            return _dt.date(value.tm_year, value.tm_mon, value.tm_mday).isoformat()
    except Exception:  # noqa: BLE001
        pass
    s = str(value)[:10]
    try:
        _dt.date.fromisoformat(s)
        return s
    except ValueError:
        return None
