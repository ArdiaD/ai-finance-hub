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

## Status

MVP. arXiv and RePEc are the reliable backbone. SSRN and Google Scholar are
best-effort (no official APIs) and isolated so a breakage can't take down a run.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design.
