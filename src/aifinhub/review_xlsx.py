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

from .config import ROOT, DB_PATH
from .db import DB
from .pdfs import promote_to_library, discard_inbox

console = Console()

REVIEW_DIR = ROOT / "review"
DECISIONS = {"yes": ("approved", False), "feature": ("approved", True),
             "no": ("rejected", None)}

# (header, attribute, width, wrap)
COLUMNS = [
    ("decision", None, 12, False),
    ("title", "title", 55, True),
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


def export_review(path: Optional[str] = None) -> Path:
    db = DB(DB_PATH)
    pending = db.query(status="pending", order="score DESC")
    if not pending:
        console.print("[yellow]No pending papers to export.[/yellow]")

    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(path) if path else REVIEW_DIR / f"inbox_{datetime.now():%Y-%m-%d}.xlsx"

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
    for r, p in enumerate(pending, start=2):
        values = {
            "title": p.title, "_authors": ", ".join(p.authors), "venue": p.venue,
            "source": p.source, "published": p.published, "score": p.score,
            "relevance_note": p.relevance_note, "abstract": p.abstract,
            "url": p.url, "pdf_url": p.pdf_url, "fingerprint": p.fingerprint,
        }
        for c, (_head, attr, _w, wrap) in enumerate(COLUMNS, 1):
            val = "" if attr is None else values.get(attr, "")
            cell = ws.cell(row=r, column=c, value=val)
            if wrap:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            else:
                cell.alignment = Alignment(vertical="top")

    # yes/no/feature dropdown on the decision column for all data rows
    dv = DataValidation(type="list", formula1='"yes,no,feature"', allow_blank=True)
    dv.error = "Pick yes, no, or feature"
    dv.prompt = "yes = include · feature = include + highlight on LinkedIn · no = reject"
    ws.add_data_validation(dv)
    last = len(pending) + 1
    dv.add(f"A2:A{max(last, 2)}")

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{max(last, 1)}"
    wb.save(out)

    console.print(
        f"[green]Exported {len(pending)} pending papers → {out}[/green]\n"
        "Open it (it's on Dropbox), fill the [bold]decision[/bold] column "
        "(yes/no/feature), save, then:\n"
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
        db.set_status(fp, status, featured=featured)
        # PDF lifecycle: keep → promote inbox→library; reject → discard from inbox.
        if status == "approved":
            moved = promote_to_library(fp)
            if moved:
                db.update_fields(fp, pdf_path=str(moved))
        else:
            discard_inbox(fp)
            db.update_fields(fp, pdf_path=None)
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
