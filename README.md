# AI & Finance Paper Hub

**Live site → https://ardiad.github.io/ai-finance-hub/**

A curated, weekly-updated collection of research at the intersection of
**artificial intelligence** and **finance** — with a focus on **trading and
investment**. New papers are discovered automatically from public repositories,
reviewed by a human, and published to a searchable, filterable web hub. A
LinkedIn post draft is generated for the week's highlights.

Curated by **David Ardia** (HEC Montréal).

---

## How it works

```
  fetch ──▶ polish ──▶ review-export ──▶ [human: yes/no] ──▶ review-import ──▶ build-site ──▶ push
 sources    enhance     dated Excel        decision          sort PDFs         GitHub Pages
```

1. **Discover** candidate papers from arXiv, RePEc, SSRN, and journal feeds.
2. **Enhance** their metadata (titles, authors, abstracts, links, dates, themes).
3. **Review** them in a dated Excel file — a human marks `yes` / `no` / `feature`.
4. **Publish** the accepted papers to the public hub; archive the rest.

The database (`data/hub.db`) is the source of truth. The public artifact is
`docs/papers.json`, which drives the static site — no build server required.

---

## The weekly workflow

```bash
# 1. Discover — scan sources, download candidate PDFs, tag themes & relevance
python -m aifinhub fetch

# 2. Enhance — fill in metadata: LLM extraction, links, sources, dates
python -m aifinhub polish

# 3. Export the review sheet (date-stamped for team tracking)
python -m aifinhub review-export
#    → data/excel/review/review_<DATE>.xlsx

#    ── HUMAN STEP ────────────────────────────────────────────────
#    Open the .xlsx (synced via Dropbox) and fill the `decision`
#    column for each paper:  yes  |  no  |  feature
#    (feature = accept AND highlight in the LinkedIn post)
#    ──────────────────────────────────────────────────────────────

# 4. Import the decisions
python -m aifinhub review-import data/excel/review/review_<DATE>.xlsx
#    ACCEPTED → PDF moved to data/pdfs/library/   (kept in the hub)
#    REJECTED → PDF moved to data/pdfs/rejected/  (archived, not deleted)

# 5. Rebuild the site, then push to publish
python -m aifinhub build-site
git add docs && git commit -m "weekly update" && git push   # or GitHub Desktop

# 6. (Optional) Draft a LinkedIn post for the week's papers
python -m aifinhub draft-post --since 7d
#    → linkedin/linkedin_<DATE>.md  (review and post manually)
```

To add papers you already have as PDFs, drop them in `data/pdfs/human_incoming/`
and run `python -m aifinhub import-pdfs` (see **Commands** below).

---

## Setup

Requires **Python 3.9+** (developed on 3.12).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

cp .env.example .env        # then add the optional API keys below
```

### Optional API keys (`.env`)

| Key | Enables |
|---|---|
| `ANTHROPIC_API_KEY` | LLM metadata extraction (`enrich`) + nicer LinkedIn drafts |
| `SEMANTIC_SCHOLAR_KEY` | Reliable URL/date lookup (no rate limits) — [free key](https://www.semanticscholar.org/product/api) |
| `CROSSREF_MAILTO` | Politeness contact for the Crossref API |
| `SERPAPI_KEY` | Google Scholar source (off by default) |

The hub works without any keys — arXiv and RePEc are the reliable backbone — but
the keys substantially improve metadata quality.

---

## Commands

| Command | What it does |
|---|---|
| `fetch` | Discover new papers from all sources; download candidate PDFs; tag themes |
| `polish` | Run all metadata-cleanup passes (enrich → backfill-urls → relabel-sources → fix-dates) |
| `review-export` | Write pending papers to `data/excel/review/review_<date>.xlsx` |
| `review-import <xlsx>` | Apply the yes/no/feature decisions; sort PDFs into library/rejected |
| `build-site` | Export approved papers to `docs/papers.json` and regenerate the site |
| `draft-post [--since 7d]` | Generate a LinkedIn post draft in `linkedin/` |
| `import-pdfs [folder]` | Import existing PDFs (default `data/pdfs/human_incoming/`) |
| `enrich` | LLM-extract title/authors/abstract for PDFs lacking an embedded id |
| `backfill-urls` | Find DOI/URL/venue by title (Crossref + arXiv + Semantic Scholar) |
| `refresh-urls` | Re-resolve links by source preference (default SSRN > arXiv > journal) |
| `relabel-sources` | Set the real source/venue (arXiv/SSRN/journal) from each URL |
| `fix-dates` | Set authoritative publication dates (arXiv id / Crossref) |
| `retag` | Re-apply the theme taxonomy to all papers |
| `reject <fingerprint>` | Reject a paper and move its PDF to `data/pdfs/rejected/` |
| `link-pdf <fingerprint> <path>` | Attach a manually downloaded PDF to a paper |
| `fetch-pdfs` | Retry downloading candidate PDFs |
| `export-xlsx [--status]` | Export the corpus to a rich Excel file |
| `stats` | Show pipeline counts |

---

## Folder layout

```
data/                     all working data (gitignored; backed up via Dropbox)
  pdfs/
    human_incoming/       PDFs you drop here to import
    claude_incoming/      PDFs the pipeline auto-fetches, awaiting review
    library/              ACCEPTED PDFs (name1_name2_name3_year.pdf)
    rejected/             REJECTED papers' PDFs (archived, not deleted)
  excel/
    review/               weekly review spreadsheets: review_<date>.xlsx
    corpus/               corpus snapshot exports
  logs/                   weekly run logs
  hub.db                  the SQLite database (source of truth)
docs/                     the published GitHub Pages site (committed)
  index.html              searchable / filterable front-end
  papers.json             the public corpus
config.yaml               sources, relevance keywords, theme taxonomy
src/aifinhub/             the pipeline code
scripts/weekly_fetch.sh   convenience script for the weekly discovery run
```

PDFs are kept **local-only** (never committed) — the public site links to the
original publisher/arXiv/SSRN page.

---

## Configuration

Everything tunable lives in [`config.yaml`](config.yaml):

- **Sources** — arXiv categories, RePEc NEP reports, SSRN queries, journal feeds.
- **Relevance** — `ai_terms` × `finance_terms` (a paper must match ≥1 of each),
  `min_score`, and optional LLM re-ranking (`use_llm`).
- **Themes** — a `theme → keywords` map; papers are auto-tagged with all matching
  themes (shown as filter chips on the site and a column in the review Excel).
  Edit it, then run `python -m aifinhub retag`.

---

## Notes

- **Source reliability:** arXiv and RePEc are the reliable backbone. SSRN and
  Google Scholar have no official APIs and are best-effort (isolated so a
  breakage can never take down a run).
- **Link preference:** when a paper exists in multiple places, the hub prefers
  the free canonical version (SSRN > arXiv > journal); `refresh-urls` enforces this.
- **Human-in-the-loop:** nothing reaches the public hub without an explicit
  `yes` in the review Excel.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design.
