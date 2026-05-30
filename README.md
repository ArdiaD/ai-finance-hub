# AI & Finance Paper Hub

A weekly pipeline that discovers new research at the intersection of **artificial
intelligence** and **finance** (with a focus on **trading & investment**), curates
it, publishes it to a public GitHub Pages site, and drafts a LinkedIn post
highlighting the selected papers.

## Pipeline

```
  fetch     →  review-export → [Excel] → review-import →  build-site   →  draft-post
  (sources)    (pending→xlsx)  yes/no    (xlsx→DB)         (GitHub Pages)   (LinkedIn)
     │              │                        │                  │              │
  inbox (DB)   review/*.xlsx            approve/reject   docs/papers.json  out/linkedin_*.md
```

1. **`fetch`** — scan all configured sources (arXiv, RePEc, SSRN, journal feeds,
   Google Scholar), normalize results, score relevance, and store *new* items in
   the local SQLite database with status `pending`.
2. **`review-export`** → fill in Excel → **`review-import`** — export pending
   papers to an `.xlsx` with a `yes`/`no`/`feature` dropdown, decide in Excel
   (synced via Dropbox), then import the decisions back. SQLite stays the source
   of truth; Excel is just the review surface. *(An interactive CLI `review` is
   also available if you prefer one-at-a-time triage.)*
3. **`build-site`** — export approved papers to `docs/papers.json` and regenerate
   the static GitHub Pages site (searchable / filterable).
4. **`draft-post`** — generate a ready-to-paste LinkedIn post for the items
   approved (or featured) in a given week.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # add optional API keys (SerpAPI, Anthropic)

python -m aifinhub fetch                      # discover new papers
python -m aifinhub review-export              # pending → review/inbox_<date>.xlsx
#   ... open the .xlsx, fill the decision column (yes/no/feature), save ...
python -m aifinhub review-import review/inbox_2026-05-30.xlsx
python -m aifinhub build-site                 # regenerate docs/ for GitHub Pages
python -m aifinhub draft-post --since 7d      # write a LinkedIn draft
```

## Configuration

All sources, categories, and relevance keywords live in [`config.yaml`](config.yaml).

**Adapting what gets retrieved** — three independent levers:
- *Where to look:* `sources.arxiv.categories`, `sources.repec.nep_reports`,
  `sources.ssrn.queries`, `sources.journals.feeds`.
- *What counts as relevant:* `relevance.ai_terms` × `relevance.finance_terms`
  (a paper must match ≥1 of each). Raise `relevance.min_score` to be stricter.
- *Quality re-ranking:* set `relevance.use_llm: true` (needs `ANTHROPIC_API_KEY`)
  to score true relevance to trading/investment 0–10 with Claude.

**Themes** — `config.yaml` has a `themes:` block mapping each theme to keywords.
Every paper is auto-tagged with all matching themes (case-insensitive substring
over title + abstract). Themes appear as a column in the Excel review and as
filter chips on the website. Edit the taxonomy anytime, then re-apply with:

```bash
python -m aifinhub retag
```

## Local PDF archive

PDFs are kept **local-only** (in `pdfs/`, gitignored — a private archive on
Dropbox, never published). The public site links to the original publisher URL.
There are two folders with a simple lifecycle:

```
  pdfs/inbox/     temporary — this week's candidates (downloaded during `fetch`),
                  read while you review.
  pdfs/library/   permanent — every KEPT paper: your existing backlog plus each
                  week's approved papers.
```

- **`fetch`** auto-downloads each candidate's PDF (when a `pdf_url` exists) into
  `pdfs/inbox/`. *(Use `fetch --no-pdfs` to skip; `fetch-pdfs` to retry later.)*
- **`review-import`** promotes KEPT papers' PDFs `inbox → library` and deletes
  REJECTED ones from the inbox.
- Papers from sources without PDF links (RePEc, most journals, SSRN) simply have
  no local PDF — attach one manually with:
  ```bash
  python -m aifinhub link-pdf <fingerprint> ~/Downloads/paper.pdf
  ```

### Importing your existing PDF collection (your backlog)

Drop your PDFs into `incoming_pdfs/`, then:

```bash
# Already-curated backlog → straight into the permanent library:
python -m aifinhub import-pdfs incoming_pdfs --status approved

# Or route them through the Excel review first (lands in the inbox):
python -m aifinhub import-pdfs incoming_pdfs
```

For each PDF it extracts the first-page text, finds a **DOI or arXiv id**, and
pulls clean metadata (title / authors / abstract) from **Crossref / arXiv**. If
no identifier is found it falls back to the filename. Imported papers skip the
relevance filter (they're hand-picked). Archived copies land in `pdfs/library/`
named `name1_name2_name3_year.pdf` (up to 3 author surnames + year). After import
you can empty `incoming_pdfs/` — the archived copies are what the DB references.

**Enriching thin imports** — PDFs without an embedded id come in with only a
filename-derived title. Fill in real title/authors/abstract with Claude (needs
`ANTHROPIC_API_KEY` in `.env`):

```bash
python -m aifinhub enrich            # all thin imports (uses Claude Haiku)
python -m aifinhub enrich --limit 3  # try a few first
```

It reads each PDF's text, extracts the metadata, re-tags themes, and renames the
library file to the surname convention now that authors are known.

## Status

MVP. arXiv and RePEc are the reliable backbone. SSRN and Google Scholar are
best-effort (no official APIs) and isolated so a breakage can't take down a run.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design.
