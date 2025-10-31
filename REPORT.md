# UWSS – Current Status Report (arXiv‑first)

## 1) Objective
Adopt a professional, compliant pipeline to harvest arXiv via official channels, download PDFs lawfully, extract content locally, and prepare for S3 storage. Keep the system universal and config‑driven for future sources (TRB/ROSA P/Crossref, etc.).

## 2) What’s implemented now
- Harvest (OAI‑PMH):
  - Command: `arxiv-harvest-oai` (resume with `resumptionToken`).
  - Fixed namespace to `oai_dc` and max stopping by processed count for fast smoke.
  - Metrics: `--metrics-out` writes JSON under `data/runs/`.
- Fetch (canonical PDF):
  - Command: `arxiv-fetch-pdf` (polite UA, throttle/jitter, retry/backoff).
  - Atomic `.part→rename`, SHA256 checksums, sidecar `meta.json` (status/headers/hash/size/time).
  - Updates DB: `local_path`, `http_status`, `mime_type`, `file_size`, `checksum_sha256`, `fetched_at`.
- Extract (local):
  - Command: `extract-full-text` to `data/content/`.
- Compliance: `arxiv-policy-snapshot` stores Identify/robots and links.

## 3) Smoke results (local SQLite)
- Harvest small: inserted 3, then 20 (pages=1, ~11–20s). Files: `data/runs/arxiv_h*.json`.
- Fetch: 1/1 then 10/10 PDFs downloaded; sidecar `arxiv_*.meta.json`. Files: `data/runs/arxiv_p*.json`.
- Extract: full text for 10. DB: `data/uwss.sqlite` updated.

## 4) How to run (repro)
```
# policy
python -m src.uwss.cli arxiv-policy-snapshot
# harvest (choose a small window)
python -m src.uwss.cli arxiv-harvest-oai --from 2024-10-01 --max 20 --resume --metrics-out data/runs/arxiv_h.json
# fetch PDFs
python -m src.uwss.cli arxiv-fetch-pdf --limit 10 --metrics-out data/runs/arxiv_p.json
# extract full text
python -m src.uwss.cli extract-full-text --db data/uwss.sqlite --content-dir data/content --limit 10
# export (domain-filtered)
python -m src.uwss.cli export --db data/uwss.sqlite --out data/export/arxiv.jsonl --require-match --oa-only
```

## 5) Architecture (summary)
- Postgres‑first (SQLite for local), config‑driven, official APIs only.
- OAI‑PMH → normalize/upsert → fetch (atomic+hash) → extract → score/export.
- Local‑first storage; S3 as a later toggle with checksums.

## 6) Next steps (stabilize & scale)
1. PDF status tracking: add `pdf_status` and `pdf_fetched_at` for clear queries.
2. Fetch hardening: HEAD size cap (`max_mb`), pinned→latest URL order, idempotency skip by SHA256; add `--dry-run`, `--since`.
3. GROBID integration: PDF→TEI/XML→JSON; store `content_path`, checksums, `extractor='grobid'`, `parse_ok/parse_errors`.
4. Precision controls: restrict arXiv sets and recent windows; export with `--require-match` keywords/negatives.
5. S3 enablement: toggle config, bucket/prefix, checksum uploads; mirror local layout to `s3://`.
6. Monitoring (optional): per‑run ledger, richer `visited_urls` (latency/error_kind).

## 7) Compliance notes
- arXiv data from OAI‑PMH; PDFs from canonical arXiv links.
- Only public/allowed content fetched; robots/Identify snapshots stored under `docs/policies/arxiv/`.


