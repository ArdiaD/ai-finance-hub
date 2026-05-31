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

The whole cycle is **two commands around a human review step**:

```bash
# 1. Discover + enhance + produce the dated review sheet
python -m aifinhub weekly
#    → data/excel/review/review_<DATE>.xlsx

#    ── HUMAN STEP ────────────────────────────────────────────────
#    Open the .xlsx (synced via Dropbox) and fill the `decision`
#    column for each paper:  yes  |  no  |  feature
#    (feature = accept AND highlight in the LinkedIn post)
#    ──────────────────────────────────────────────────────────────

# 2. Apply decisions, rebuild the site, and draft the LinkedIn post
python -m aifinhub publish data/excel/review/review_<DATE>.xlsx

# 3. Push docs/ (GitHub Desktop) to publish, then post linkedin/linkedin_<DATE>.md
```

What the two commands expand to:

| `weekly` | `publish` |
|---|---|
| `fetch` — scan sources, download candidate PDFs, tag themes & relevance | `review-import` — apply yes/no/feature; sort PDFs into `library/` / `rejected/` |
| `polish` — enhance the new candidates' metadata (links, sources, dates) | `build-site` — regenerate `docs/papers.json` + the site |
| `review-export` — write the dated review spreadsheet | `draft-post` — write the LinkedIn draft to `linkedin/` |

Each underlying command can still be run on its own (see **Commands**).

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
| **`weekly`** | **The weekly run: fetch → polish → review-export (the dated Excel)** |
| **`publish <xlsx>`** | **Apply decisions → build-site → LinkedIn draft** |
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
