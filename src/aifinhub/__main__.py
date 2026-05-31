"""CLI entrypoint:  python -m aifinhub <command>"""

from __future__ import annotations

import argparse
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="aifinhub", description="AI & Finance Paper Hub pipeline"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # ── High-level weekly workflow ──
    sub.add_parser("weekly",
                   help="fetch → polish → review-export (produces the dated review Excel)")
    pub = sub.add_parser("publish",
                         help="review-import → build-site → draft-post (then push + post)")
    pub.add_argument("xlsx", help="the reviewed .xlsx file")

    ft = sub.add_parser("fetch", help="discover new papers from all sources")
    ft.add_argument("--no-pdfs", action="store_true",
                    help="skip downloading candidate PDFs into the inbox")
    sub.add_parser("review", help="curate the pending inbox (interactive CLI)")

    rx = sub.add_parser("review-export", help="write pending papers to an Excel file")
    rx.add_argument("--out", default=None,
                    help="output .xlsx path (default data/excel/review/review_<date>.xlsx)")
    ri = sub.add_parser("review-import", help="read yes/no/feature decisions from Excel")
    ri.add_argument("path", help="the reviewed .xlsx file")

    fp = sub.add_parser("fetch-pdfs",
                        help="(re)download candidate PDFs into data/pdfs/claude_incoming/")
    fp.add_argument("--status", default="pending",
                    choices=["approved", "pending", "all"],
                    help="which papers to download PDFs for (default pending)")

    ip = sub.add_parser("import-pdfs", help="import a folder of existing PDFs")
    ip.add_argument("folder", nargs="?", default="data/pdfs/human_incoming",
                    help="folder with PDFs (default data/pdfs/human_incoming, recursive)")
    ip.add_argument("--status", default="pending", choices=["pending", "approved"],
                    help="pending → inbox + Excel review (default); "
                         "approved → straight into the permanent library")

    lp = sub.add_parser("link-pdf", help="attach a manually downloaded PDF to a paper")
    lp.add_argument("fingerprint", help="paper fingerprint (see the Excel/stats)")
    lp.add_argument("path", help="path to the PDF file")

    en = sub.add_parser("enrich",
                        help="LLM-extract metadata for thin imported PDFs")
    en.add_argument("--limit", type=int, default=None, help="cap how many to process")
    en.add_argument("--model", default=None, help="override the extraction model")

    bf = sub.add_parser("backfill-urls",
                        help="find DOI/URL/venue by title via Crossref + arXiv")
    bf.add_argument("--limit", type=int, default=None, help="cap how many to process")

    rf = sub.add_parser("refresh-urls",
                        help="re-resolve links with a source preference (SSRN>arXiv>journal)")
    rf.add_argument("--prefer", default="ssrn,arxiv,journal",
                    help="comma-separated source priority order")
    rf.add_argument("--status", default="approved",
                    choices=["approved", "pending", "all"])

    sub.add_parser("relabel-sources",
                   help="set source/venue (arXiv/SSRN/journal) from each paper's URL")
    sub.add_parser("fix-dates",
                   help="set authoritative publication dates (arXiv id / Crossref)")
    sub.add_parser("polish",
                   help="run all metadata cleanup passes: enrich → backfill-urls "
                        "→ relabel-sources → fix-dates")

    rj = sub.add_parser("reject", help="reject papers by fingerprint + delete their PDFs")
    rj.add_argument("fingerprints", nargs="+", help="one or more paper fingerprints")

    ex = sub.add_parser("export-xlsx", help="export the corpus to a rich Excel file")
    ex.add_argument("--status", default="approved",
                    choices=["approved", "pending", "rejected", "all"])
    ex.add_argument("--out", default=None, help="output .xlsx path")

    sub.add_parser("retag", help="re-apply the theme taxonomy to all papers")
    sub.add_parser("build-site", help="export approved papers + regenerate site")

    dp = sub.add_parser("draft-post", help="write a LinkedIn draft")
    dp.add_argument("--since", default="7d", help="lookback window, e.g. 7d or 2026-05-01")
    dp.add_argument("--no-llm", action="store_true", help="use the template, skip the LLM")

    sub.add_parser("stats", help="show pipeline counts")

    args = parser.parse_args(argv)

    if args.cmd == "weekly":
        from .workflows import weekly
        weekly()
    elif args.cmd == "publish":
        from .workflows import publish
        publish(args.xlsx)
    elif args.cmd == "fetch":
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
    elif args.cmd == "enrich":
        from .enrich import enrich, DEFAULT_MODEL
        enrich(limit=args.limit, model=args.model or DEFAULT_MODEL)
    elif args.cmd == "reject":
        from .pdfs import reject_papers
        n = reject_papers(args.fingerprints)
        print(f"rejected {n}")
    elif args.cmd == "backfill-urls":
        from .backfill import backfill_urls
        backfill_urls(limit=args.limit)
    elif args.cmd == "refresh-urls":
        from .backfill import refresh_urls
        refresh_urls(prefer=tuple(args.prefer.split(",")), status=args.status)
    elif args.cmd == "relabel-sources":
        from .backfill import relabel_sources
        relabel_sources()
    elif args.cmd == "fix-dates":
        from .backfill import fix_dates
        fix_dates()
    elif args.cmd == "polish":
        from .polish import polish
        polish()
    elif args.cmd == "export-xlsx":
        from .corpus_xlsx import export_corpus
        export_corpus(status=args.status, path=args.out)
    elif args.cmd == "retag":
        from .themes import retag_all
        retag_all()
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
