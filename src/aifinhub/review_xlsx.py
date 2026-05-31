"""Excel review bridge.

SQLite stays the source of truth; Excel is just the human review surface:

  review-export  →  write pending papers to an .xlsx with a yes/no/feature
                    dropdown in the first column (open it on Dropbox, decide).
  review-import  →  read the decisions back and update SQLite.

Decision values: yes = approve, feature = approve + highlight on LinkedIn,
no = reject, blank = leave pending (re-appears in the next export).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from rich.console import Console

from .config import DB_PATH, EXCEL_REVIEW_DIR
from .db import DB

console = Console()

REVIEW_DIR = EXCEL_REVIEW_DIR
DECISIONS = {"yes": ("approved", False), "feature": ("approved", True),
             "no": ("rejected", None)}

# (header, attribute, width, wrap)
COLUMNS = [
    ("decision", None, 12, False),
    ("title", "title", 55, True),
    ("themes", "_themes", 26, True),
    ("authors", "_authors", 30, True),
    ("venue", "venue", 22, True),
    ("source", "source", 14, False),
    ("published", "published", 12, False),
    ("score", "score", 8, False),
    ("why", "relevance_note", 28, True),
    ("abstract", "abstract", 80, True),
    ("url", "url", 40, False),
    ("pdf_url", "pdf_url", 30, False),
    ("fingerprint", "fingerprint", 18, False),  # key — do not edit
]


def _decision_for(paper) -> str:
    """Pre-fill the decision cell from a paper's current status (for --all)."""
    if paper.status == "approved":
        return "feature" if paper.featured else "yes"
    if paper.status == "rejected":
        return "no"
    return ""  # pending → undecided


def export_review(path: Optional[str] = None, all_papers: bool = False) -> Path:
    db = DB(DB_PATH)
    if all_papers:
        rows = db.query(order="published DESC, score DESC")  # whole database
        prefill = True
    else:
        rows = db.query(status="pending", order="score DESC")  # weekly: new only
        prefill = False
    if not rows:
        console.print("[yellow]No papers to export.[/yellow]")

    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    if path:
        out = Path(path)
    elif all_papers:
        out = REVIEW_DIR / f"database_{datetime.now():%Y-%m-%d}.xlsx"
    else:
        out = REVIEW_DIR / f"review_{datetime.now():%Y-%m-%d}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "review"

    # Header row
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(bold=True, color="FFFFFF")
    for c, (head, *_rest) in enumerate(COLUMNS, 1):
        cell = ws.cell(row=1, column=c, value=head)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(c)].width = COLUMNS[c - 1][2]

    # Data rows
    for r, p in enumerate(rows, start=2):
        values = {
            "title": p.title, "_themes": ", ".join(p.themes),
            "_authors": ", ".join(p.authors), "venue": p.venue,
            "source": p.source, "published": p.published, "score": p.score,
            "relevance_note": p.relevance_note, "abstract": p.abstract,
            "url": p.url, "pdf_url": p.pdf_url, "fingerprint": p.fingerprint,
        }
        for c, (_head, attr, _w, wrap) in enumerate(COLUMNS, 1):
            if attr is None:  # the decision column
                val = _decision_for(p) if prefill else ""
            else:
                val = values.get(attr, "")
            cell = ws.cell(row=r, column=c, value=val)
            cell.alignment = Alignment(wrap_text=wrap, vertical="top")

    # yes/no/feature dropdown on the decision column for all data rows
    dv = DataValidation(type="list", formula1='"yes,no,feature"', allow_blank=True)
    dv.error = "Pick yes, no, or feature"
    dv.prompt = "yes = include · feature = include + highlight on LinkedIn · no = reject"
    ws.add_data_validation(dv)
    last = len(rows) + 1
    dv.add(f"A2:A{max(last, 2)}")

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{max(last, 1)}"
    wb.save(out)

    what = "all" if all_papers else "pending"
    console.print(
        f"[green]Exported {len(rows)} {what} papers → {out}[/green]\n"
        "Open it (it's on Dropbox), edit the [bold]decision[/bold] column "
        "(yes = in hub · feature = in + highlight · no = out), save, then:\n"
        f"  [bold]python -m aifinhub review-import '{out}'[/bold]"
    )
    return out


def import_review(path: str) -> dict:
    db = DB(DB_PATH)
    wb = load_workbook(path, read_only=True)
    ws = wb["review"] if "review" in wb.sheetnames else wb.active

    rows = ws.iter_rows(values_only=True)
    header = [str(h).strip().lower() if h else "" for h in next(rows)]
    try:
        i_dec = header.index("decision")
        i_fp = header.index("fingerprint")
    except ValueError:
        raise SystemExit("Spreadsheet missing 'decision' or 'fingerprint' column.")

    stats = {"approved": 0, "featured": 0, "rejected": 0, "skipped": 0, "missing": 0}
    for row in rows:
        if not row or i_fp >= len(row):
            continue
        fp = str(row[i_fp]).strip() if row[i_fp] else ""
        decision = str(row[i_dec]).strip().lower() if row[i_dec] else ""
        if not fp:
            continue
        if decision not in DECISIONS:
            stats["skipped"] += 1
            continue
        if not db.get(fp):
            stats["missing"] += 1
            continue
        status, featured = DECISIONS[decision]
        # The PDF stays in the library; accepting/rejecting only flips the flag.
        db.set_status(fp, status, featured=featured)
        if decision == "feature":
            stats["featured"] += 1
        elif decision == "yes":
            stats["approved"] += 1
        else:
            stats["rejected"] += 1

    console.print(
        f"[green]Imported decisions:[/green] approved={stats['approved']} "
        f"featured={stats['featured']} rejected={stats['rejected']} "
        f"left-pending={stats['skipped']}"
        + (f" [red]missing-fp={stats['missing']}[/red]" if stats["missing"] else "")
    )
    console.print("Next: [bold]python -m aifinhub build-site[/bold]")
    return stats
