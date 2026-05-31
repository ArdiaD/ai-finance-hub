"""High-level weekly workflow commands that bundle the individual steps.

  weekly   = fetch → polish (new papers) → review-export   → produces the dated
             review Excel for the human yes/no/feature decision.
  publish  = review-import → build-site → draft-post        → sorts PDFs, rebuilds
             the site, and writes the LinkedIn draft. You then push + post.
"""

from __future__ import annotations

from rich.console import Console

console = Console()


def weekly() -> None:
    """Discover + enhance new candidates, then export the review spreadsheet."""
    console.rule("[bold cyan]WEEKLY · 1/3  fetch[/bold cyan]")
    from .fetch import run_fetch
    run_fetch()

    console.rule("[bold cyan]WEEKLY · 2/3  polish (new papers)[/bold cyan]")
    from .polish import polish
    polish(status="pending")  # only enhance the freshly-fetched candidates

    console.rule("[bold cyan]WEEKLY · 3/3  review-export[/bold cyan]")
    from .review_xlsx import export_review
    path = export_review()

    console.print("\n[bold green]Weekly run complete.[/bold green]")
    console.print(f"  1. Open [bold]{path}[/bold] and fill the decision column "
                  "(yes / no / feature).")
    console.print(f"  2. Then run: [bold]python -m aifinhub publish '{path}'[/bold]")


def publish(xlsx: str) -> None:
    """Apply the review decisions, rebuild the site, and draft the LinkedIn post."""
    console.rule("[bold cyan]PUBLISH · 1/3  review-import[/bold cyan]")
    from .review_xlsx import import_review
    import_review(xlsx)

    console.rule("[bold cyan]PUBLISH · 2/3  build-site[/bold cyan]")
    from .export import build_site
    build_site()

    console.rule("[bold cyan]PUBLISH · 3/3  draft-post[/bold cyan]")
    from .linkedin import draft_post
    draft_post(since="7d")

    console.print("\n[bold green]Publish complete.[/bold green]")
    console.print("  1. Push [bold]docs/[/bold] (GitHub Desktop) to update the live hub.")
    console.print("  2. Review & post the draft in [bold]linkedin/[/bold] on LinkedIn.")
