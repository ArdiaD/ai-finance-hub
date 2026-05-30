"""One-shot metadata cleanup: run all post-import enrichment passes in order.

  1. enrich          — LLM-extract title/authors/abstract for thin PDFs (needs key)
  2. backfill-urls   — find DOI/URL/venue by title (Crossref + arXiv + S2)
  3. relabel-sources — set real source/venue (arXiv/SSRN/journal) from the URL
  4. fix-dates       — authoritative publication dates (arXiv id / Crossref)

Order matters: enrich gives clean titles → backfill matches on them → relabel and
fix-dates use the resolved URLs. Each pass only touches what still needs work, so
`polish` is safe to re-run.
"""

from __future__ import annotations

from rich.console import Console

from .config import env

console = Console()


def polish() -> None:
    console.rule("[bold]1/4  enrich[/bold]")
    if env("ANTHROPIC_API_KEY"):
        from .enrich import enrich, DEFAULT_MODEL
        enrich(model=DEFAULT_MODEL)
    else:
        console.print("[yellow]skipped — set ANTHROPIC_API_KEY in .env to enable[/yellow]")

    from .backfill import backfill_urls, relabel_sources, fix_dates

    console.rule("[bold]2/4  backfill-urls[/bold]")
    backfill_urls()

    console.rule("[bold]3/4  relabel-sources[/bold]")
    relabel_sources()

    console.rule("[bold]4/4  fix-dates[/bold]")
    fix_dates()

    console.print("\n[bold green]Polish complete.[/bold green] "
                  "Next: [bold]python -m aifinhub build-site[/bold]")
