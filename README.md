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
 sources    enhance     dated Excel        decision          set in/out flag   GitHub Pages
```

1. **Discover** candidate papers from arXiv, RePEc, SSRN, and a curated set of
   finance & ML/AI journals (via OpenAlex).
2. **Enhance** their metadata (titles, authors, abstracts, links, dates, themes).
3. **Review** them in a dated Excel file — a human marks `yes` / `no` / `feature`.
4. **Publish** the accepted papers to the public hub.

Every paper is also scored for **FAME relevance** (embedding similarity to a
research-project summary — see [FAME relevance scoring](#fame-relevance-scoring)).

The database (`data/hub.db`) is the source of truth; every paper's PDF lives in
one folder (`data/pdfs/library/`) and a status flag decides whether it appears on
the hub. The public artifact is `docs/papers.json`, which drives the static
site — no build server required.

---

## The weekly workflow

The whole cycle is **two commands around a human review step**:

```bash
# 1. Discover + enhance + produce the dated review sheet
python -m aifinhub weekly
#    → data/excel/<DATE>_hub_db.xlsx   (a dated full-DB snapshot)

#    ── HUMAN STEP ────────────────────────────────────────────────
#    Open the .xlsx (synced via Dropbox) and fill the `decision`
#    column for each paper:  yes  |  no  |  feature
#    (feature = accept AND highlight in the LinkedIn post)
#    ──────────────────────────────────────────────────────────────

# 2. Apply decisions, rebuild the site, and draft the LinkedIn post
python -m aifinhub publish data/excel/<DATE>_hub_db.xlsx

# 3. Push docs/ (GitHub Desktop) to publish, then post linkedin/linkedin_<DATE>.md
```

What the two commands expand to:

| `weekly` | `publish` |
|---|---|
| `fetch` — scan sources, download candidate PDFs, tag themes & relevance | `review-import` — apply yes/no/feature (flips each paper's in-hub flag) |
| `polish` — enhance the new candidates' metadata (links, sources, dates) | `build-site` — regenerate `docs/papers.json` + the site |
| `review-export` — write the dated review spreadsheet | `draft-post` — write the LinkedIn draft to `linkedin/` |

Each underlying command can still be run on its own (see **Commands**).

To add papers you already have as PDFs, drop them in `data/pdfs/incoming/`
and run `python -m aifinhub import-pdfs` (see **Commands** below).

**The database snapshot.** `review-export` writes a dated **full-database
snapshot** — `data/excel/<DATE>_hub_db.xlsx` — every paper with an editable
`decision` column pre-filled from its current state (`yes` = in the hub,
`feature` = in + highlighted, `no` = not on the hub). It's both the review
surface and the weekly archival record. To add or remove any paper by hand, edit
its `decision` cell and re-import:

```bash
python -m aifinhub review-export             # → data/excel/<date>_hub_db.xlsx
#   ... flip decision cells: yes (add) / no (remove) / feature (highlight) ...
python -m aifinhub review-import data/excel/<date>_hub_db.xlsx
python -m aifinhub build-site
```

A fresh snapshot is also written automatically after each `weekly` run and each
`import-pdfs`, so `data/excel/` becomes a week-by-week history of the database.

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
| `review-export` | Write a dated full-DB snapshot (`data/excel/<date>_hub_db.xlsx`) |
| `review-import <xlsx>` | Apply the yes/no/feature decisions (flips each paper's in-hub flag) |
| `build-site` | Export approved papers to `docs/papers.json` and regenerate the site |
| `draft-post [--since 7d]` | Generate a LinkedIn post draft in `linkedin/` |
| `import-pdfs [folder]` | Import existing PDFs (default `data/pdfs/incoming/`) |
| `enrich` | LLM-extract title/authors/abstract for PDFs lacking an embedded id |
| `backfill-urls` | Find DOI/URL/venue by title (Crossref + arXiv + Semantic Scholar) |
| `refresh-urls` | Re-resolve links by source preference (default SSRN > arXiv > journal) |
| `relabel-sources` | Set the real source/venue (arXiv/SSRN/journal) from each URL |
| `fix-dates` | Set authoritative publication dates (arXiv id / Crossref) |
| `retag` | Re-apply the theme taxonomy to all papers |
| `fame-score [--rescore]` | Score each paper's similarity to the FAME project (see below) |
| `reject <fingerprint>` | Mark a paper out of the hub (its PDF stays in the library) |
| `link-pdf <fingerprint> <path>` | Attach a manually downloaded PDF to a paper |
| `fetch-pdfs` | Retry downloading candidate PDFs |
| `stats` | Show pipeline counts |

---

## Folder layout

```
data/                     all working data (gitignored; backed up via Dropbox)
  pdfs/
    incoming/             PDFs you drop here to import
    library/              EVERY paper's PDF (name1_name2_name3_year.pdf) — whether
                          a paper is in the hub is a DB flag, not which folder
  excel/                  dated full-DB snapshots: <date>_hub_db.xlsx
                          (review surface + weekly archival record)
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

- **Sources** — arXiv categories, RePEc NEP reports, SSRN queries, and the
  **OpenAlex venue source**: a curated list of finance/quant journals (searched
  for AI terms) and ML/AI journals (searched for finance terms). Add or remove
  venues under `sources.openalex` — each is an OpenAlex source id (`S…`).
- **Relevance** — `ai_terms` × `finance_terms` (a paper must match ≥1 of each),
  `min_score`, and optional LLM re-ranking (`use_llm`).
- **Themes** — a `theme → keywords` map; papers are auto-tagged with all matching
  themes (shown as filter chips on the site and a column in the review Excel).
  Edit it, then run `python -m aifinhub retag`.

---

## The hub website

The static site (`docs/`) loads `papers.json` and runs entirely client-side
(no server). Visitors get, over the curated corpus:

- full-text **search** (title · authors · abstract);
- filters by **theme**, **source**, and a **year range** (from / to);
- **sort** by *newest first* or *most FAME-relevant*;
- each card shows the venue, year (month precision), **theme chips**, an
  expandable abstract, and — where relevant — a **`FAME · NN%`** badge.

`papers.json` is fetched with a content-hash cache-buster so the site always
shows the latest data after a rebuild.

---

## FAME relevance scoring

The hub doubles as a live literature map for the **FAME** research project
(*Financial Artificial Machine Intelligence* — Dauphine–PSL × HEC Montréal, on
Generative AI / LLMs in investing & trading). `fame-score` rates how close each
paper is to that project, surfaced as the **`FAME · NN%`** badge on the site, a
*most FAME-relevant* sort option, and a `fame_score` column in the Excel snapshot.

It is a pure **embedding-similarity** measure (no LLM judgment), computed locally
and offline:

1. The project summary in **`fame/FAME.md`** is embedded with a local
   `sentence-transformers` model (`all-MiniLM-L6-v2`, free, no API key).
2. Each paper's **title + abstract** is embedded the same way.
3. Their **cosine similarity** — rescaled onto 0–100% so same-domain papers
   spread out — is the FAME score.

Core GenAI-in-finance papers land near 100%; tangential work near 0%. Re-run
after editing the summary or adding papers (the badge threshold is
`FAME_THRESHOLD` in `src/aifinhub/fame.py`):

```bash
pip install -e ".[fame]"            # one-time: installs sentence-transformers
python -m aifinhub fame-score       # scores only new/unscored papers
python -m aifinhub fame-score --rescore   # re-scores everything (after editing FAME.md)
python -m aifinhub build-site
```

*(`fame/` is private and gitignored — it holds the project summary, not committed
to the public repo.)*

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
