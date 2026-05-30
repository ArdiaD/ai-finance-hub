"""CLI entrypoint:  python -m aifinhub <command>"""

from __future__ import annotations

import argparse
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="aifinhub", description="AI & Finance Paper Hub pipeline"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    ft = sub.add_parser("fetch", help="discover new papers from all sources")
    ft.add_argument("--no-pdfs", action="store_true",
                    help="skip downloading candidate PDFs into the inbox")
    sub.add_parser("review", help="curate the pending inbox (interactive CLI)")

    rx = sub.add_parser("review-export", help="write pending papers to an Excel file")
    rx.add_argument("--out", default=None, help="output .xlsx path (default review/inbox_<date>.xlsx)")
    ri = sub.add_parser("review-import", help="read yes/no/feature decisions from Excel")
    ri.add_argument("path", help="the reviewed .xlsx file")

    fp = sub.add_parser("fetch-pdfs",
                        help="(re)download candidate PDFs into pdfs/inbox/")
    fp.add_argument("--status", default="pending",
                    choices=["approved", "pending", "all"],
                    help="which papers to download PDFs for (default pending)")

    ip = sub.add_parser("import-pdfs", help="import a folder of existing PDFs")
    ip.add_argument("folder", help="folder containing the PDFs (searched recursively)")
    ip.add_argument("--status", default="pending", choices=["pending", "approved"],
                    help="pending → inbox + Excel review (default); "
                         "approved → straight into the permanent library")

    lp = sub.add_parser("link-pdf", help="attach a manually downloaded PDF to a paper")
    lp.add_argument("fingerprint", help="paper fingerprint (see the Excel/stats)")
    lp.add_argument("path", help="path to the PDF file")

    sub.add_parser("build-site", help="export approved papers + regenerate site")

    dp = sub.add_parser("draft-post", help="write a LinkedIn draft")
    dp.add_argument("--since", default="7d", help="lookback window, e.g. 7d or 2026-05-01")
    dp.add_argument("--no-llm", action="store_true", help="use the template, skip the LLM")

    sub.add_parser("stats", help="show pipeline counts")

    args = parser.parse_args(argv)

    if args.cmd == "fetch":
        from .fetch import run_fetch
        run_fetch(download_pdfs=not args.no_pdfs)
    elif args.cmd == "review":
        from .review import run_review
        run_review()
    elif args.cmd == "review-export":
        from .review_xlsx import export_review
        export_review(args.out)
    elif args.cmd == "review-import":
        from .review_xlsx import import_review
        import_review(args.path)
    elif args.cmd == "fetch-pdfs":
        from .pdfs import download_pdfs
        download_pdfs(status=args.status)
    elif args.cmd == "import-pdfs":
        from .ingest_pdf import import_pdfs
        import_pdfs(args.folder, status=args.status)
    elif args.cmd == "link-pdf":
        from .pdfs import link_pdf
        link_pdf(args.fingerprint, args.path)
    elif args.cmd == "build-site":
        from .export import build_site
        build_site()
    elif args.cmd == "draft-post":
        from .linkedin import draft_post
        draft_post(since=args.since, use_llm=not args.no_llm)
    elif args.cmd == "stats":
        from .config import DB_PATH
        from .db import DB
        print(DB(DB_PATH).counts())
    return 0


if __name__ == "__main__":
    sys.exit(main())
