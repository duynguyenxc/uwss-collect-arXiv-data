## UWSS — Project Report (arXiv-first, Phases 1–4)

### 1) What I tried first (old version) and why it was a problem

#### Old approach (algorithm & architecture)
- I crawled HTML landing pages and guessed the PDF links (from abs → pdf) or followed third-party links (e.g., from Crossref) to download files.
- The core “algorithm” was: discover a page → try to detect a pdf_url or fallback to source_url → HTTP GET → guess MIME → save as .pdf or .html.
- The architecture had a generic downloader (“download open links”), thin logging, no strict file integrity, and limited dedup rules. It did not pin arXiv versions.

#### Problems I hit
- Policy misalignment: I had not read each source’s policy carefully. That made the collection less “official”.
- Fragile scraping: HTML structure changed; no official resume mechanism; stop conditions were ad‑hoc.
- Low reproducibility: I often fetched the latest arXiv PDF (not version‑pinned), so results could change over time.
- Weak integrity & provenance: I did not compute a file hash every time, did not always cap size by HEAD, and sidecar files were inconsistent.

#### Lesson learned & decision
- I must read and follow the policy of each source and use official channels when they exist.
- I decided to rebuild with an arXiv‑first design using OAI‑PMH for metadata and canonical arXiv PDF rules. Then I can extend the same design to TRB/TRID, FHWA, ERDC, and other sources.
- I reviewed prior successful community projects that relied on OAI‑PMH and canonical PDF policies to shape my pipeline and apply those practices here.

### 2) What I do now (current official approach)

#### Goal
Build a universal, policy‑aligned pipeline that is stable, reproducible, and easy to extend to new sources.

#### Current architecture (simple and reliable)
- Database as source of truth (SQLite for local runs; a Postgres path is ready for scale).
- Config + CLI pipeline with idempotent steps and checkpoints:
  - Harvest (arXiv OAI‑PMH) → Normalize → Upsert into documents
  - Score/Filter (two‑stage precision by keywords, with negatives and title boost)
  - Fetch PDFs (canonical, version‑pinned → latest; HEAD size cap; atomic write; SHA256)
  - (Optional) Extract content (GROBID) → TEI/XML → JSON
  - Export (JSONL/CSV, manifests, metrics)
  - Upload to S3 (PDF + identification files)
  - Observability: metrics JSON, validation, quick QA commands, recent downloads, and a global manifest.
  - My current keyword configuration focuses on the “concrete deterioration” domain; I can switch topics by editing the keyword list and negatives.

#### How it collects data (algorithmic details)
- OAI‑PMH harvest: I use ListRecords with `oai_dc`, parse arXiv ID, DOI, title, authors, abstract, year, landing URL, and a canonical `pdf_url`.
- Two‑stage precision: I run a keyword scorer (with negative terms) and export only IDs that require a match and pass a year filter. Then I fetch PDFs only for those IDs.
- Fetch strategy: try version‑pinned `IDvN.pdf` first (reproducible), fallback to latest `ID.pdf`, and finally any explicit `pdf_url` if present.
- Network hygiene & integrity: throttle + jitter, retry/backoff, HEAD size cap, atomic `.part → rename`, SHA256 checksum, rich sidecar JSON next to each PDF, and a `visited_urls` registry for provenance.
- Idempotency & resume: resumption token in harvest, safe upserts, and clear `pdf_status` + `pdf_fetched_at`.
  - I persist checkpoints in `ingestion_state` (for resumption token) and keep a `visited_urls` table to record first/last seen and status codes.

### 3) arXiv harvesting today (status, issues, lessons)

#### Runs I actually completed
- Small pass: attempted 100 → downloaded 98, `404 = 2`.
- Big pass (recent):
  - Harvest: inserted 200 in one pass; failed = 0.
  - Scoring: 950 docs scored.
  - Export with `--require-match --year-min 1995`: 936 IDs.
  - Fetch first 200 IDs: attempted 49 → downloaded 47, `404 = 2` (others were already on disk → skipped). HEAD size cap enforced; no timeouts in that run.
  - Validation: clean (no duplicate DOI/title; no missing core fields; no broken files).
  - Year distribution: skewed to recent years (2022=208, 2023=209, 2024=273) — expected for my keywords.

#### Issues I saw and how I handled them
- `404` for some items (withdrawn/renamed or old links): I record `pdf_status=not_found`.
- Windows shell quirks for slicing ID files (PowerShell): I fixed the commands and re‑ran.
- S3 pathing/region: after I created the bucket and user policy properly, uploads completed fine.

### 4) What data I collect and store (very important, detailed)

#### Database table `documents` includes
- Identification: internal `id`, `source` (arxiv), `arxiv_id`, `doi`, `title`, `authors`, `venue`, `year`, `abstract`, optional `topic`.
- File & provenance: `local_path`, `mime_type`, `http_status`, `file_size`, `checksum_sha256`, `status`, `pdf_status`, `fetched_at`, `pdf_fetched_at`, `url_hash_sha1`.
- (Optional extraction fields): `content_path`, `content_chars`, `text_excerpt` (to be filled after GROBID).

#### Sidecar next to every PDF (`*.meta.json`)
- Who/what: `document_id`, `source`, `arxiv_id`, `doi`, `title`, `authors[]`, `abstract`, `year`, optional `topic`.
- How/when fetched: `pdf_status`, `http_status`, `pdf_fetched_at`, `file_size`, `checksum_sha256`, `url_used`, `etag`/`last_modified` (when available), and later `s3_key`.
- Purpose: when I open a folder (locally or on S3), I can identify the PDF immediately and see the fetch provenance without opening the DB.

#### Global manifest (audit file)
- `manifest.jsonl` (one line per document) contains identification + provenance. I use it for quick audits, checks, and human review.
- This data model meets the professor’s requirement: metadata (identification) + full‑text PDF + (soon) extracted content with clear provenance.

### 5) S3 work I finished

- Bucket/Region: `uwss-data-duy` in `us-east-1`.
- What I uploaded:
  - Earlier batch: 439 objects ~ 1.2 GiB to `s3://uwss-data-duy/uwss/clean/`.
  - Newer/larger batch: same layout, more items uploaded (one earlier command reported “Uploaded 677 files…”, which includes PDFs and JSON artifacts).
- Layout (human‑readable “by-id”):
  - `uwss/clean/by-id/<document_id>/pdf.pdf`
  - `uwss/clean/by-id/<document_id>/pdf.meta.json`
  - `uwss/clean/by-id/<document_id>/doc.json`
  - optional (future): `uwss/clean/by-id/<document_id>/content.json` or `/tei.xml`
- Metadata: I backfill `s3_key` into sidecars and add basic S3 object metadata (`document_id`, `doi/arxiv_id`, `title`, `year`, `sha256`) so each object is self‑describing.
- Next S3 hardening I will do: Lifecycle rules (Standard‑IA after 30 days; Glacier after 90). S3 Inventory (daily) for audit. Optional: store SHA256 as S3 object tag and upload a batch‑level manifest to S3.

#### 5.1) Additional assurances for the meeting
- Compliance evidence: I also saved arXiv policy snapshots (OAI‑PMH Identify and robots.txt) under `docs/policies/arxiv/`.
- Precision quick‑check: I manually spot‑checked ~20 recent PDFs; about ~90% looked clearly on‑topic by title/abstract. I will refine this percentage with a larger sample after the meeting.
- Cost & lifecycle: Current stored data is a few GiB (earlier clean run ≈1.2 GiB + recent uploads). At S3 Standard in us‑east‑1 (~$0.023/GB‑month) the monthly cost is well under one dollar; I plan to enable Lifecycle (30‑day → Standard‑IA, 90‑day → Glacier).

### 6) Terms I actually use in the system
- OAI‑PMH: official protocol I use to harvest arXiv metadata with ListRecords (`oai_dc`).
- Canonical PDF: arXiv PDF fetched from `arxiv.org/pdf/...` with version‑pinned first (`IDvN.pdf`), then latest (`ID.pdf`) for reproducibility.
- Sidecar: a `*.meta.json` file next to each PDF with identification + fetch provenance (status, time, size, sha256, url, `s3_key`).
- Manifest: a global `*.jsonl` audit file listing identification + provenance for all documents.
- GROBID (optional, next): service to convert PDFs to TEI/XML and clean text so I can store `content_path` and richer fields.

### 7) How to run (the exact sequence I used)

Example (SQLite, PowerShell on Windows):
```powershell
# 1) Harvest ~200 items (OAI-PMH)
python -m src.uwss.cli arxiv-harvest-oai ^
  --db data\uwss_clean.sqlite ^
  --from 2024-01-01 --until 2025-11-01 --max 200 --resume ^
  --metrics-out data\runs_clean\arxiv_h_big.json --log-json

# 2) Score by keywords (two-stage precision)
python -m src.uwss.cli score-keywords ^
  --db data\uwss_clean.sqlite ^
  --config config\config.yaml

# 3) Export with require-match + year filter and write IDs
python -m src.uwss.cli export ^
  --db data\uwss_clean.sqlite ^
  --out data\export_clean\arxiv_big.jsonl ^
  --require-match --skip-missing-core --year-min 1995 ^
  --ids-out data\export_clean\filtered_ids_big.txt

# 4) Fetch PDFs for first 200 IDs (atomic write, SHA256, sidecars)
Get-Content data\export_clean\filtered_ids_big.txt | Select-Object -First 200 | `
  Set-Content data\export_clean\ids_200.txt -Encoding Ascii
python -m src.uwss.cli arxiv-fetch-pdf ^
  --db data\uwss_clean.sqlite ^
  --outdir data\files_clean ^
  --limit 200 ^
  --ids-file data\export_clean\ids_200.txt ^
  --max-mb 60 ^
  --metrics-out data\runs_clean\arxiv_p_big.json --log-json

# 5) QA (validation and stats)
python -m src.uwss.cli validate ^
  --db data\uwss_clean.sqlite ^
  --json-out data\export_clean\validation_big.json
python -m src.uwss.cli stats ^
  --db data\uwss_clean.sqlite ^
  --json-out data\export_clean\stats_big.json

# 6) Export a global manifest for audit
python -m src.uwss.cli export-manifest ^
  --db data\uwss_clean.sqlite ^
  --out data\export_clean\manifest.jsonl

# 7) Upload to S3, by-id layout (PDF + sidecars + doc.json)
python -m src.uwss.cli s3-upload ^
  --db data\uwss_clean.sqlite ^
  --files-dir . ^
  --bucket uwss-data-duy ^
  --prefix uwss/clean_large/ ^
  --region us-east-1 ^
  --include-sidecars --include-docjson --include-content ^
  --layout by-id
```

### 8) Current accuracy, relevance, and quality
- DB coverage: ~950 arXiv records (open‑access = true).
- Recent batch (first 200 IDs): attempted 49, downloaded 47, `404 = 2` (others already existed → skipped).
- Validation: no duplicate DOI/title; no missing core fields; no broken file links.
- Relevance: I control it with keyword scoring + negatives at export time and `--require-match`. This gives me a clean candidate list to fetch.

### 11) Git workflow (branch and commits)
- I keep work on the GitHub repository `duynguyenxc/uwss-upgrade` and push to the branch `improvement-uwss` after each stable phase.
- Latest commits include: enriched sidecars, `export-manifest` CLI, S3 uploader (by‑id layout with doc.json/sidecars), and large‑run artifacts for QA.

### 12) Appendix — concrete errors I fixed during implementation
- `ImportError` for `VisitedUrl` export: I added the missing export to the store package.
- Schema drift: I added migrations/CLI guard to create `pdf_status` and `pdf_fetched_at` when missing.
- `UNIQUE constraint failed: visited_urls.url`: I switched to safe merge/upsert logic to avoid duplicate inserts in a single session.
- A stray `IndentationError` in `db.py`: I fixed it so CLI imports run cleanly.
- PowerShell pipeline mistakes when slicing ID lists: I corrected the syntax and re‑ran the fetch step.

### 9) What I will improve next
- S3 hardening: lifecycle + inventory; optional SHA256 object tag; per‑batch manifest on S3.
- Sidecar refresh: regenerate sidecars for already‑downloaded PDFs without refetching.
- Postgres path: when volume or concurrency grows (>100k docs or many parallel jobs), switch to Postgres/RDS and wire all CLI steps via `--db-url`; add indexes.
- GROBID extraction: add TEI/XML and clean text into `content_path` so I can search inside documents and produce better exports.
- New source adapters (official‑first): reuse the same pattern for TRB/TRID, FHWA, ERDC, ROSA P. For paywalled sources (ASCE/ACI/TRR), I will store metadata + DOI and use Unpaywall/OpenAlex to find OA versions when possible.

### 10) One-paragraph summary
I rebuilt my system from a brittle HTML‑scraping tool into an arXiv‑first, policy‑aligned pipeline that uses OAI‑PMH for discovery and canonical arXiv PDF rules for stable, reproducible files. I added strong identification in sidecars and a global manifest, strict fetch controls (HEAD size cap, atomic writes, SHA256, explicit `pdf_status`), two‑stage precision (export IDs → fetch), and S3 uploads in a clear by‑id layout. My latest runs show clean validation, recent‑year coverage, and hundreds of objects uploaded to S3 with rich identification. I am ready to harden S3 lifecycle, scale to Postgres, integrate GROBID for content extraction, and extend the same “official‑first” approach to TRB/TRID, FHWA, and ERDC.



