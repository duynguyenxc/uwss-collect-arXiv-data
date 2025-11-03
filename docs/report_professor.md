## UWSS — Comprehensive Report (arXiv‑first, Phase 1–4)

### 1) Executive summary
- We transitioned from ad‑hoc scraping to an official, reproducible arXiv‑first pipeline: OAI‑PMH harvesting → canonical PDF fetching (version‑pinned→latest) → optional GROBID → scoring/export → S3 upload.
- Data quality hardened: HEAD size cap, atomic writes, SHA256, `pdf_status`/`pdf_fetched_at`, improved `visited_urls`, two‑stage precision, metrics and quick QA commands.
- Cloud handoff verified: uploaded 439 PDF objects (~1.2 GiB) to `s3://uwss-data-duy/uwss/clean/` (us‑east‑1).

### 2) Before vs After (non‑official → official arXiv)
#### 2.1 Non‑official approach (historical)
- Seed crawl / HTML scraping of landing pages; infer `pdf_url` from `abs` pages; sometimes jump via external links (e.g., Crossref) directly to PDFs.
- Not version‑pinned, weaker provenance, and harder to respect robots/rate limits. Fetch logic depended on opportunistic `pdf_url`/`source_url` detection and MIME guesses.

Code that reflects the generic open‑link downloader (historical utility):
```178:285:src/uwss/crawl/__init__.py
def download_open_links(db_path: Path, out_dir: Path, limit: int = 10, contact_email: Optional[str] = None, db_url: Optional[str] = None) -> int:
    # ... prefer pdf_url if present, else source_url; throttle/jitter; MIME guess; save as .pdf/.html
    q = session.execute(select(Document).where((Document.open_access == True) & ((Document.local_path == None) | (Document.local_path == ""))))
    # ... HTTP GET + status accounting; Retry-After; detect PDF by headers/filename; write file
```

Issues: brittle parsing, not formally aligned with arXiv policies, limited reproducibility.

#### 2.2 Official arXiv approach (current)
- Discover via OAI‑PMH (ListRecords, `oai_dc`), normalize identifiers (arXiv ID, DOI), then fetch canonical PDFs: try version‑pinned `IDvN.pdf` first, then latest `ID.pdf`.
- HEAD size cap to avoid large files; robust status mapping to `pdf_status`; atomic `.part→rename`; SHA256 and sidecar meta; improved visited‑url provenance; throttle+jitter.

OAI‑PMH parse (correct namespaces; count processed for `--max`):
```25:48:src/uwss/arxiv/harvest_oai.py
def _parse_oai_record(record_el: ET.Element) -> Dict[str, Any]:
    ns = {
        "oai": "http://www.openarchives.org/OAI/2.0/",
        "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    # ... parse identifiers/title/abstract/dates; extract arXiv id & DOI; build landing/pdf_url
```

```126:173:src/uwss/arxiv/harvest_oai.py
inserted = 0; processed = 0
# ... loop over records; count processed, cap by max_records; upsert dedup by arXiv ID/DOI/title
```

Canonical PDF fetching (pinned→latest; HEAD size cap; status/metrics):
```52:69:src/uwss/fetch/arxiv_pdf.py
def _candidate_pdf_urls(landing_url: Optional[str], pdf_url: Optional[str]) -> list[str]:
    # Prefer version-pinned URL first for reproducibility, then latest; keep explicit pdf_url last
```

```141:176:src/uwss/fetch/arxiv_pdf.py
# HEAD Content-Length cap, record visited, skip 403/404; support dry_run; choose candidate
```

### 3) Core data model, migrations, and CLI
- `Document` now maintains PDF‑specific fields and integrity metadata:
```14:56:src/uwss/store/models.py
class Document(Base):
    # ... core bibliographic fields ...
    status: Mapped[str] = mapped_column(String(40), default="not_fetched")
    pdf_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    pdf_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    url_hash_sha1: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
```

- Lightweight migrations ensure back‑compat for SQLite (similar will be wired for Postgres when needed):
```38:90:src/uwss/store/db.py
def migrate_db(db_path: Path) -> None:
    # ... adds pdf_status, pdf_fetched_at, checksum_sha256, url_hash_sha1, etc.; ensures registry tables
```

- S3 upload command (optional phase):
```1001:1015:src/uwss/cli.py
# s3-upload: upload files by Document.local_path to s3://<bucket>/<prefix>
```

### 4) Algorithms — what changed and why it matters
- Harvest (OAI‑PMH): deterministic discovery, idempotent upsert; resume via `resumptionToken`; stop by processed count to avoid paging forever on duplicates.
- Fetch (canonical):
  - URL order: pinned `IDvN.pdf` → latest `ID.pdf` → explicit `pdf_url` (if any).
  - HEAD size cap (configurable `--max-mb`), dry‑run, since‑days filtering; atomic `.part→rename` to avoid partial files.
  - Integrity: SHA256 computation; sidecar `*.meta.json`; update `pdf_status`, `pdf_fetched_at`, `http_status`, `file_size`, `mime_type`.
  - Provenance: `visited_urls` upsert to avoid unique violations.
- Two‑stage precision: `export --ids-out` (with `--require-match`, year filters) → `arxiv-fetch-pdf --ids-file`.

### 5) Observability and QA artifacts (evidence)
- Metrics JSON (recent final pass examples):
  - `data/runs_clean/arxiv_h_final.json`: inserted 100, pages=1, failed=0.
  - `data/runs_clean/arxiv_p_final.json`: attempted 100, downloaded 98, 404=2.
  - `data/runs_clean/summary_final.json`: ledger across harvest/fetch runs.
- Dataset stats/validation:
  - `data/export_clean/stats_final.json`: total 550, OA 550; by_year peaks 2022–2024.
  - `data/export_clean/validation_final.json`: no dup DOI/title; no missing core; no broken paths.
- Export set used for precision review:
  - `data/export_clean/arxiv_final.jsonl` (540 records) + `filtered_ids_final.txt`.

### 6) S3 integration (what we stored & how)
- Verified upload to `s3://uwss-data-duy/uwss/clean/` (region us‑east‑1):
  - Summary: 439 objects, ~1.2 GiB (confirmed via `aws s3 ls ... --summarize`).
  - Objects are canonical PDFs named `arxiv_*.pdf`, corresponding to `Document.local_path` entries from the clean run.
- CLI used (for operator reference):
```1001:1015:src/uwss/cli.py
# s3-upload --bucket uwss-data-duy --prefix uwss/clean/ --region us-east-1
```
- Next S3 hardening (planned):
  - Upload sidecars `*.meta.json`, attach SHA256 as S3 object tag/metadata, generate `manifest.json` for audit/restore.
  - Lifecycle: Standard‑IA after 30 days, Glacier after 90 days; enable daily S3 Inventory.

### 7) Errors encountered and fixes (key items)
- Import/export visibility: added `VisitedUrl` to store init to resolve `ImportError`.
- Schema drift: ensured `pdf_status` / `pdf_fetched_at` migrations; added CLI guard to add columns.
- Unique URL collisions: switched to safe upsert/merge for `visited_urls` to avoid `UNIQUE constraint failed`.
- Indentation errors: fixed in `db.py` so CLI imports succeed across modules.
- CLI completeness: added arguments for `--metrics-out`, recent‑downloads, runs‑summary.

### 8) How to reproduce (operator quick script)
- Clean run (example):
```1:36:docs/runbook_phase3.md
## Phase 3 Runbook (arXiv‑first)
# arxiv-harvest-oai --from ... --max 200 --resume --metrics-out data/runs_clean/arxiv_h.json --log-json
# arxiv-fetch-pdf   --outdir data/files_clean --limit 200 --metrics-out data/runs_clean/arxiv_p.json --log-json
```

### 9) Universality and next steps
- Design is universal‑ready (config‑driven, idempotent, dedupe, scoring) and supports multiple sources; arXiv pipeline is production‑grade.
- Next priorities:
  1) S3 hardening (sidecars+manifest+SHA256 tags, lifecycle, inventory).
  2) Optional Postgres path for bigger scale and concurrent jobs; add indexes and full CLI `--db-url` support for score/export/fetch/extract.
  3) GROBID integration runbook and parsing ledger.
  4) Source adapters (TRB/ROSA‑P/Europe PMC/OpenAlex re‑enable) with the same policies and QA hooks.

---
Prepared for the professor: exhaustive evidence (metrics, exports), algorithmic diffs, and code citations pinpointing the compliant arXiv‑first implementation.


