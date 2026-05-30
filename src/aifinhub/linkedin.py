"""Generate a ready-to-paste LinkedIn post from recently approved papers."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from rich.console import Console

from .config import load_config, DB_PATH, LINKEDIN_DIR, env
from .db import DB

console = Console()


def _parse_since(since: str) -> str:
    """'7d' / '14d' / 'YYYY-MM-DD' → ISO cutoff date string."""
    if m := re.fullmatch(r"(\d+)d", since):
        return (date.today() - timedelta(days=int(m.group(1)))).isoformat()
    return since


def _select(db: DB, cutoff: str):
    approved = db.query(status="approved", order="featured DESC, published DESC")
    recent = [p for p in approved if (p.fetched_at or "") >= cutoff]
    featured = [p for p in recent if p.featured]
    # If nothing was explicitly featured, highlight the top-scored recent few.
    if not featured:
        featured = sorted(recent, key=lambda p: p.score, reverse=True)[:5]
    return recent, featured


def _template_post(cfg, featured, n_total) -> str:
    hub = cfg["hub"]
    lines = [
        f"📈 This week in AI × Finance — {len(featured)} papers worth your time",
        "",
        f"New additions to the {hub['title']} ({n_total} papers added this week):",
        "",
    ]
    for p in featured:
        authors = p.authors[0] + (" et al." if len(p.authors) > 1 else "")
        lines.append(f"🔹 {p.title}")
        lines.append(f"   {authors} · {p.venue or p.source}")
        lines.append(f"   {p.url}")
        lines.append("")
    lines.append(f"👉 Browse the full hub: {hub['site_url']}")
    lines.append("")
    lines.append("#AI #MachineLearning #Finance #QuantitativeFinance #Investing #Trading")
    return "\n".join(lines)


def _llm_post(cfg, featured, n_total) -> str | None:
    api_key = env("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    items = "\n\n".join(
        f"Title: {p.title}\nAuthors: {', '.join(p.authors)}\n"
        f"Venue: {p.venue or p.source}\nURL: {p.url}\nAbstract: {p.abstract[:600]}"
        for p in featured
    )
    prompt = (
        "Write a concise, engaging LinkedIn post (max ~180 words) for a research "
        "curator highlighting these new papers on AI for trading & investment. "
        "Lead with a hook, give one-line takeaways per paper, include the URLs, "
        f"end with a link to the hub ({cfg['hub']['site_url']}) and 4-6 hashtags. "
        "Professional but lively; no emojis overload (2-4 max).\n\n" + items
    )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=cfg["relevance"]["llm_model"], max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:  # noqa: BLE001
        return None


def draft_post(since: str = "7d", use_llm: bool = True) -> None:
    cfg = load_config()
    db = DB(DB_PATH)
    cutoff = _parse_since(since)
    recent, featured = _select(db, cutoff)

    if not recent:
        console.print(f"[yellow]No approved papers since {cutoff}.[/yellow]")
        return

    post = (_llm_post(cfg, featured, len(recent)) if use_llm else None) \
        or _template_post(cfg, featured, len(recent))

    LINKEDIN_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = LINKEDIN_DIR / f"linkedin_{stamp}.md"
    path.write_text(post + "\n")
    console.print(f"[green]Draft written → {path}[/green]\n")
    console.print(post)
