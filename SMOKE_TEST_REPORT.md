# Smoke Test Report (local)

## PG-first large-run (Phase A–E) — Latest
### Commands
```powershell
# Env (UA rotation; no proxy)
$env:UWSS_UA_FILE = "config/user_agents.txt"

# Indexes
python -m src.uwss.cli --db-url $env:UWSS_DB_URL db-create-indexes

# Discover
python -m src.uwss.cli --db-url $env:UWSS_DB_URL discover-semanticscholar --config config/config.yaml --max 100 --cache-ttl-sec 86400 --log-json
python -m src.uwss.cli --db-url $env:UWSS_DB_URL discover-eupmc --config config/config.yaml --max 50 --cache-ttl-sec 86400 --log-json

# Score (with negative keywords)
python -m src.uwss.cli --db-url $env:UWSS_DB_URL score-keywords --config config/config.yaml --negative-keywords-file config/ai_keywords.txt

# Fetch + Extract
python -m src.uwss.cli --db-url $env:UWSS_DB_URL fetch --limit 100 --config config/config.yaml --log-json
python -m src.uwss.cli --db-url $env:UWSS_DB_URL extract-full-text --content-dir data/content --limit 100

# Validate + Export
python -m src.uwss.cli --db-url $env:UWSS_DB_URL validate --json-out data/export/pg_smoke_validate.json
python -m src.uwss.cli --db-url $env:UWSS_DB_URL export --out data/export/pg_smoke_large.jsonl --require-match --negative-keywords-file config/ai_keywords.txt --log-json
```

### Results summary
- Discover: +55 (S2), +0 (EUPMC) với cấu hình keyword hiện tại.
- Score: 70 bản ghi cập nhật.
- Fetch: Enriched OA 34; Downloaded 11 (một số 403 từ publisher, chấp nhận được khi không dùng proxy).
- Extract: 63 bản ghi có `content_path/content_chars`.
- Validate: `dup_title` = 0; nhóm `dup_doi` phản ánh DOI rỗng (không phải trùng DOI thực).
- Export: 68 bản ghi ra `data/export/pg_smoke_large.jsonl` (require-match + negative keywords).

### Observations
- Pipeline Postgres chạy ổn định; logging/metrics rõ ràng.
- Resolver cải thiện PDF hit-rate (meta-refresh + selector phổ biến).
- UA rotation đã bật; có thể tăng thêm proxy để giảm 403 khi mở rộng quy mô.

## Scope
- Validate critical path end-to-end on small samples: migrate → discover (Crossref/EUPMC/S2/arXiv) → enrich+fetch → scrape-full-content → export.
- Ensure incremental resume works and identification fields are complete.

## Commands used
```powershell
# 0) Migrate
python -m src.uwss.cli db-migrate --db data/uwss.sqlite

# 1) Discover (small samples)
python -m src.uwss.cli discover-crossref --config config/config.yaml --db data/uwss.sqlite --max 5 --cache-ttl-sec 86400
python -m src.uwss.cli discover-eupmc --config config/config.yaml --db data/uwss.sqlite --max 5 --cache-ttl-sec 86400
python -m src.uwss.cli discover-semanticscholar --config config/config.yaml --db data/uwss.sqlite --max 3 --cache-ttl-sec 86400
python -m src.uwss.cli discover-arxiv --config config/config.yaml --db data/uwss.sqlite --max 3 --resume

# 2) Enrich + fetch small
python -m src.uwss.cli fetch --db data/uwss.sqlite --outdir data/files --limit 2 --config config/config.yaml

# 3) Scrape full content for URLs
python -m src.uwss.cli scrape-full-content --db data/uwss.sqlite --content-dir data/content --limit 2 --config config/config.yaml

# 4) Export JSONL (embed full_content for verification)
python -m src.uwss.cli export --db data/uwss.sqlite --out data/export/smoke_small.jsonl \
  --include-provenance --include-full-text --skip-missing-core --embed-content
```

## Results (this run)
- Migrate: OK
- Crossref (max 5): Inserted 0 (cache/filters) → No error
- Europe PMC (max 5): Inserted 0 → No error
- Semantic Scholar (max 3): Inserted 2 → OK (batched per keyword to avoid 400)
- arXiv (max 3, resume): Inserted 2 → OK
- Enrich+Fetch (limit 2): Enriched 19 via Unpaywall; Downloaded 2 files (1×403 observed but handled)
- Scrape full content (limit 2): OK
- Export JSONL: Exported 146 records to `data/export/smoke_small.jsonl`

## Identification completeness
- Export includes: id, doi, title, authors, venue, year/date, source/source_url/landing_url, pdf_url, pdf_path, abstract, content_path, content_chars, full_content (when `--embed-content`), open_access, license, oa_status, provenance.

## API + Scrapy Coordination (short plan)
- Shared registry/state: `visited_urls` + `ingestion_state` unify incremental across APIs & Scrapy.
- Priority queue: API discoveries seed high-quality landing URLs; Scrapy respects whitelist/blacklist from config.
- Consistent throttling/retry: align per-host throttle + backoff.
- Unified export surface: JSONL/CSV/S3 with one schema.



