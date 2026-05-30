"""Interactive CLI to validate the inbox.

For each pending paper: [a]pprove, [f]eature (approve + highlight in LinkedIn),
[r]eject, [s]kip (leave pending), [o]pen in browser, [q]uit.
"""

from __future__ import annotations

import webbrowser

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from .config import load_config, DB_PATH
from .db import DB

console = Console()


def _render(paper, idx, total) -> Panel:
    authors = ", ".join(paper.authors[:6]) + ("…" if len(paper.authors) > 6 else "")
    cats = " ".join(paper.categories[:5])
    body = (
        f"[bold]{paper.title}[/bold]\n"
        f"[dim]{authors}[/dim]\n"
        f"[yellow]{paper.venue or paper.source}[/yellow]  ·  "
        f"published: {paper.published or '?'}  ·  "
        f"score: [bold]{paper.score:g}[/bold]\n"
        f"[dim italic]{paper.relevance_note}[/dim italic]\n\n"
        f"{paper.abstract[:600]}{'…' if len(paper.abstract) > 600 else ''}\n\n"
        f"[blue underline]{paper.url}[/blue underline]"
    )
    return Panel(body, title=f"[{idx}/{total}]  {paper.source}  ·  {cats}",
                 border_style="cyan")


def run_review() -> None:
    load_config()
    db = DB(DB_PATH)
    pending = db.query(status="pending", order="score DESC")
    if not pending:
        console.print("[green]Inbox empty — nothing to review.[/green]")
        return

    total = len(pending)
    console.print(f"[bold]{total}[/bold] papers to review.\n")
    for i, paper in enumerate(pending, 1):
        console.print(_render(paper, i, total))
        while True:
            choice = Prompt.ask(
                "[a]pprove [f]eature [r]eject [s]kip [o]pen [q]uit",
                choices=["a", "f", "r", "s", "o", "q"],
                default="s",
            )
            if choice == "o":
                webbrowser.open(paper.url)
                continue
            break
        if choice == "q":
            console.print("[yellow]Stopped.[/yellow]")
            break
        if choice == "a":
            db.set_status(paper.fingerprint, "approved", featured=False)
        elif choice == "f":
            db.set_status(paper.fingerprint, "approved", featured=True)
        elif choice == "r":
            db.set_status(paper.fingerprint, "rejected")
        # 's' leaves it pending
        console.print()

    c = db.counts()
    console.print(
        f"\n[bold]Status:[/bold] approved={c.get('approved', 0)} "
        f"rejected={c.get('rejected', 0)} pending={c.get('pending', 0)}"
    )
    console.print("Next: [bold]python -m aifinhub build-site[/bold]")
