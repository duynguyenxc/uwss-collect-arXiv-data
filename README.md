# UWSS – Universal Web‑Scraping System (arXiv‑first)

Universal, config‑driven harvesting pipeline. Current focus: official arXiv integration using OAI‑PMH for metadata and canonical PDF download, with safe, reproducible operations.

## Key ideas
- Postgres‑first (or SQLite for local): database is the single source of truth.
- Config‑driven: keywords, throttling, email/UA are set in `config/config.yaml`.
- Official sources only: arXiv OAI‑PMH for metadata, canonical `arxiv.org/pdf/...` for PDFs.
- Idempotent + resume: checkpoints and upserts allow safe re‑runs.
- Local‑first files: PDFs and extracted content are stored on disk; S3 upload is optional.

## Quick start
1) Optional: validate config
```
python -m src.uwss.cli config-validate --config config/config.yaml
```
2) Snapshot arXiv policy artifacts (compliance)
```
python -m src.uwss.cli arxiv-policy-snapshot
```
3) Harvest a small batch via OAI‑PMH
```
python -m src.uwss.cli arxiv-harvest-oai --from 2024-10-01 --max 20 --resume --metrics-out data/runs/arxiv_h.json
```
4) Download PDFs (canonical arXiv URLs)
```
python -m src.uwss.cli arxiv-fetch-pdf --limit 10 --metrics-out data/runs/arxiv_p.json
```
Note: fetcher tries version‑pinned URL first (e.g. `.../pdf/IDvN.pdf`) then latest (`.../pdf/ID.pdf`) for reproducibility.
5) Extract full text (local PDF → text)
```
python -m src.uwss.cli extract-full-text --db data/uwss.sqlite --content-dir data/content --limit 10
```
6) Export (JSONL/CSV)
```
python -m src.uwss.cli export --db data/uwss.sqlite --out data/export/arxiv.jsonl --require-match --oa-only
```

Precision controls examples:
```
# Harvest a narrow window and category
python -m src.uwss.cli arxiv-harvest-oai --from 2024-10-01 --until 2024-10-07 --set cs --max 50 --resume
# Export requiring keyword match (from scoring)
python -m src.uwss.cli export --db data/uwss.sqlite --out data/export/filtered.jsonl --require-match --year-min 1995
```

Tips
- Throttling: set `UWSS_THROTTLE_SEC` and `UWSS_JITTER_SEC` (e.g., 1.0 / 0.5) for polite pacing.
- Postgres instead of SQLite: add `--db-url $env:UWSS_DB_URL` to any command.

## Where data goes
- DB: `data/uwss.sqlite` (or Postgres via `--db-url`). Tables: `documents`, `visited_urls`, `ingestion_state`.
- PDFs: `data/files/arxiv_*.pdf` with sidecar `arxiv_*.meta.json` (status, headers, SHA256).
- Extracted content: `data/content/` (text from PDF/HTML; Phase 3 adds GROBID TEI/JSON).
- Metrics: `data/runs/*.json` when `--metrics-out` is provided.
- Policy: `docs/policies/arxiv/` (Identify, robots, links).

## Architecture (current)
- Harvest: arXiv OAI‑PMH (ListRecords) → parse DC → normalize → upsert to DB (resume via resumptionToken).
- Fetch: canonical PDF with retry/backoff + throttle/jitter; atomic `.part→rename`; SHA256 + meta.json.
- Extract: local PDF/HTML → text; stores `content_path` and basic stats (Phase 3 adds GROBID).
- Score/export: keyword scoring + negatives → export JSONL/CSV.

## Configuration
See `config/config.yaml`:
- `contact_email`, `user_agent`: used for polite UA across requests.
- `rate_limits.throttle_sec/jitter_sec`: default pacing.
- `domain_keywords/negative_keywords`: used by scoring/export.
- Optional arXiv window via CLI `--from/--until`; sets can be passed with `--set`.

## Roadmap (short)
- Phase 3: GROBID integration (PDF → TEI/XML → structured JSON), store `content_path`, checksums, `extractor='grobid'`.
- Phase 4: S3 enablement (bucket/prefix toggle), checksums, optional requester‑pays for arXiv bulk.
- Hardening: `pdf_status`/`pdf_fetched_at`, HEAD size cap, pinned→latest order, `--dry-run`/`--since`.

## Compliance
- Only public/allowed content is fetched.
- arXiv metadata via OAI‑PMH; PDFs via canonical arXiv links.
- Policy snapshot stored under `docs/policies/arxiv`.



