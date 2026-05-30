# Architecture

```
                        ┌──────────────────────────────────────────┐
   weekly trigger  ───▶ │  fetch                                    │
   (manual / cron)      │   sources/*  →  normalize  →  relevance   │
                        │              →  dedup       →  SQLite     │
                        └──────────────────────────────────────────┘
                                          │  status = pending
                                          ▼
                        ┌──────────────────────────────────────────┐
   human-in-the-loop ─▶ │  review  (CLI)                            │
                        │   approve / feature / reject              │
                        └──────────────────────────────────────────┘
                                          │  status = approved
                          ┌───────────────┴────────────────┐
                          ▼                                 ▼
              ┌───────────────────────┐        ┌────────────────────────┐
              │  build-site           │        │  draft-post            │
              │  docs/papers.json     │        │  out/linkedin_*.md     │
              │  docs/index.html      │        │  (paste manually)      │
              │  → GitHub Pages       │        └────────────────────────┘
              └───────────────────────┘
```

## Components

| Module | Responsibility |
|---|---|
| `sources/*` | One plugin per source. Each returns a list of normalized `Paper`s. Failures are isolated — a broken source never aborts the run. |
| `models.Paper` | Canonical record + dedup fingerprint (arXiv id / DOI / SSRN id, else title hash). |
| `relevance` | Keyword AND-gate (AI term × finance term) + optional Claude re-ranking. |
| `fetch` | Orchestrates sources, scores, fuzzy-dedups against the DB, stores `pending`. |
| `db` (SQLite) | Working source of truth: dedup, status, fetch log. |
| `review` | Human curation CLI. |
| `export` + `site` | Emits `docs/papers.json` and a static, searchable `index.html`. |
| `linkedin` | Drafts a post from the week's approved/featured papers. |

## Design choices

- **Two reliable backbones (arXiv, RePEc/NEP)** carry the pipeline; SSRN and
  Google Scholar are best-effort and fully isolated.
- **DB vs. committed data:** `hub.db` is local working state (gitignored). The
  *public* artifact is `docs/papers.json`, which is committed and drives the site.
  This keeps the community repo clean and reviewable.
- **Human-in-the-loop is mandatory** between discovery and publishing — nothing
  reaches the public hub or LinkedIn without an explicit approve.
- **No-build static site:** `index.html` fetches `papers.json` client-side, so
  GitHub Pages needs zero CI to serve it.

## Dedup strategy

1. Strong identifier match (arXiv id / DOI / SSRN id) via fingerprint.
2. Fuzzy title match (`token_sort_ratio ≥ 92`) catches preprint↔published pairs.

## Extending

Add a source: drop `sources/<name>.py` exposing
`fetch(source_cfg, fetch_cfg) -> list[Paper]`, register it in
`sources/__init__.py`, and add a `sources.<name>` block to `config.yaml`.
