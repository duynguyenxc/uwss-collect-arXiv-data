<!-- ## Universal Web-Scraping System (UWSS) — Summary Report (English)

### Table of contents
- Weekly summary (10/20–10/26)
- deduplication and relevance
- Quick start (Postgres / SQLite)
- Appendix: Setup Postgres local (Windows)
- 1) Project goals (simple)
- 2) How the system works (end-to-end)
- 3) Data sources
- 4) Output example
- 5) Run many times without duplicates
- 6) Why Postgres-first?
- 7) Database and data types
- 8) Simple configuration
- 9) Quality and observability
- 10) Conclusion
- Appendix: Example flow
- References and inspirations

### Weekly summary (10/20–10/26)
- Research and choose DB: Completed — PostgreSQL chosen as the main database (PG-first); SQLite for local dev. Added `--db-url`, created helpful indexes, verified export works the same.
- Collect lots of data (pdf, post/article, html, summary, API, abstract): In progress — pipeline runs well; I collected many records from APIs (Semantic Scholar gives the most), downloaded PDFs/HTML, and extracted text. I can scale more with extra keywords and proxy.
- Fix OpenAlex API error: Completed — OpenAlex disabled; other API issues (Semantic Scholar 400) solved by batching per keyword.
- Find relevant sources with full identification: Completed — integrated S2/Europe PMC/Crossref/arXiv/PMC/DOAJ; export includes id, title, authors, year/date, source/urls, pdf_url/pdf_path, content_path, license, oa_status.
- Survey paid sources (access rules and cost): Not started — waiting for the target list.
- Optimize pipeline (rate-limit, retry/backoff, detect PDF vs HTML, prevent duplication): Completed — throttle/jitter and retries; Unpaywall enrich; resolver with meta-refresh and PDF selectors; downloader detects PDF by Content-Type/Disposition; dedupe by DOI/title/url_hash; visited URL registry and in-batch dedupe.
- Cloud run / save to cloud: Partially ready — Dockerfile exists; S3 upload command exists (SQLite variant). I can add PG `--db-url` variant and full deploy steps next.
- Plan for 10/27: Try a cloud-backed run and store outputs to cloud, then document the steps and results.
The plan for next week is to try to continue exploring more sources to collect more quality data, try to fix errors when running and storing on the cloud, learn and integrate more proxies for better optimization.

### For new readers: start here
- If you just want to test quickly, go to "Quick start" (Postgres or SQLite).
- If you need to install Postgres, see "Appendix: Setup Postgres local (Windows)".
- If you want to understand how it works, see "2) How the system works" and the "Appendix: Example flow".

### deduplication and relevance
- Deduplication: check in order DOI → Title (case-insensitive) → url_hash_sha1 (SHA1 of PDF/landing). If a match is found, only fill missing fields (e.g., pdf_url/local_path); do not insert a new row. Checkpoints (`ingestion_state`) plus `--resume` skip old pages. Fetch/Extract are idempotent (fill only when missing). `visited_urls` + in-batch guard prevent duplicate URL inserts.
- Relevance: `domain_keywords` drive API queries. The scorer uses tokens and bigrams on title/abstract (title weighted higher). `negative_keywords` lower scores for off-topic items; export can use `--require-match` to keep only relevant results.

### Challenges and resolutions (this week)
- Setup to save data to Postgres takes quite a while
- Fixing duplicate errors and finding relevant data takes a lot of time
- OpenAlex API unstable → disabled; focus on stable sources (S2/EUPMC/Crossref/arXiv/PMC/DOAJ).
- Semantic Scholar 400 (query too long) → batch by keyword with small pages; add cache TTL and warnings.
- PostgreSQL string too long (VARCHAR) → safe clipping for `title` (1000), `venue` (255), `topic` (100) during discover.
- `--db-url` confusion → use as a global flag before subcommands; examples added.
- Code errors (Indent/Syntax) → fixed in CLI and crawl during refactors.
- UniqueViolation in `visited_urls` → added per-run `visited_seen` and update-or-insert; no more errors.
- HTTP 403 from some publishers → mitigate with UA rotation, throttle/jitter, retries; proxy recommended at scale.

- Dependencies → ensured `psycopg2-binary`, `PyYAML`; clean `requirements.txt`.

### 1) Project goals (simple)
- Discover academic items for “reinforced concrete deterioration” from open sources (Semantic Scholar, Europe PMC, Crossref, arXiv, PMC, DOAJ).
- Download open PDF/HTML when possible, extract text, and export JSONL with full identification fields (ID, DOI, Title, Authors, Year, Source URL, Landing URL, PDF URL, PDF Path, Content Path, Open Access, License, etc.).
- Run many times without duplicate data thanks to deduplication and checkpoint.

#### Deduplication and checkpoint (short explanation + example)
- Deduplication: before inserting into `documents`, check in this order:
  1) DOI match → same item, do not insert new row
  2) If no DOI, match Title (case-insensitive)
  3) If still missing, use `url_hash_sha1` (SHA1 of PDF/Landing URL)
  If a match exists, only fill missing fields (for example add `pdf_url` or `local_path`) instead of creating a new record.
  Example: Run 1 finds DOI=10.1186/… (no PDF yet). Run 2 sees same DOI with a PDF URL → update the old row’s `pdf_url`, no new row (same ID).

- Checkpoint (resume): for each source, save paging state in table `ingestion_state` (offset/cursor/page). With `--resume`, the next discover run continues from the saved position.
  Example: `discover-semanticscholar --max 50` inserts 50 rows and saves offset=50. Next run with `--resume` starts from row 51.

- Visited URLs (for download/resolve): every fetched/resolved URL is saved in `visited_urls` (first_seen/last_seen/status). Also dedupe inside one run to avoid duplicate inserts.
  Example: a PDF URL already downloaded (has `local_path`) will not be re-downloaded; only `last_seen` updates.

### 2) How the system works (end-to-end)
1. Discover (find candidates via APIs):
   - Sources: Semantic Scholar (main), Europe PMC, Crossref, arXiv, PMC, DOAJ.
   - Read keywords from `config/config.yaml` → call APIs → insert into Postgres `documents` table.
   - Avoid duplicates by DOI → title → url_hash.
2. Score (relevance by keywords):
   - Token/bigram on title/abstract; title has higher weight.
   - Negative keywords (from config) help filter out unrelated items.
3. Fetch (download) + Resolve (better links):
   - Unpaywall enrich: get OA, license, best PDF/landing.
   - Resolve publisher: follow “View via Publisher”, detect PDF via meta/link.
   - Download: save to `data/files/`, update `local_path`, checksum, mime type…
4. Extract (full text):
   - Read PDF/HTML, save plain text to `data/content/`, update `content_path`, `content_chars`.
5. Export (final data):
   - Export JSONL/CSV from Postgres with filters (for example `--require-match`).

Quick start (two options: Postgres or SQLite)

Notes:
- Use Windows PowerShell in the project folder (for example `D:\uwss`).
- If you do not have Postgres, use B) SQLite. If you have Postgres, I suggest A).

A) Run with Postgres (recommended)
```powershell
# 0) Python environment
cd D:\uwss
python -m venv .venv
.\.venv\Scripts\Activate
python -m pip install -U pip
pip install -r requirements.txt

# 1) Set DB URL (change user/password/port/db if needed)
$env:UWSS_DB_URL = "postgresql+psycopg2://postgres:123456@localhost:5432/uwss"
echo $env:UWSS_DB_URL

# 2) enable User-Agent rotation
$env:UWSS_UA_FILE = "config/user_agents.txt"

# 3) Create indexes
python -m src.uwss.cli --db-url $env:UWSS_DB_URL db-create-indexes

# 4) Discover a small batch (increase --max later)
python -m src.uwss.cli --db-url $env:UWSS_DB_URL discover-semanticscholar --config config/config.yaml --max 50 --cache-ttl-sec 86400 --log-json

# 5) Score by keywords in config.yaml
python -m src.uwss.cli --db-url $env:UWSS_DB_URL score-keywords --config config/config.yaml

# 6) Download + enrich/resolve (increase --limit later)
python -m src.uwss.cli --db-url $env:UWSS_DB_URL fetch --limit 20 --config config/config.yaml --log-json

# 7) Extract full text
python -m src.uwss.cli --db-url $env:UWSS_DB_URL extract-full-text --content-dir data/content --limit 20

# 8) Export JSONL
python -m src.uwss.cli --db-url $env:UWSS_DB_URL export --out data/export/run_latest.jsonl --require-match --log-json
```

If your folder is not `D:\uwss`, change it to your path. If Postgres uses a different port or password, change `UWSS_DB_URL` accordingly.

B) Run with SQLite (no Postgres)
```powershell
# 0) Python environment
cd D:\uwss
python -m venv .venv
.\.venv\Scripts\Activate
python -m pip install -U pip
pip install -r requirements.txt

# 1) Init SQLite file (creates data/uwss.sqlite)
python -m src.uwss.cli db-init --db data/uwss.sqlite

# 2) Discover (insert directly into SQLite)
python -m src.uwss.cli discover-semanticscholar --config config/config.yaml --db data/uwss.sqlite --max 50 --cache-ttl-sec 86400 --log-json

# 3) Score
python -m src.uwss.cli score-keywords --config config/config.yaml --db data/uwss.sqlite

# 4) Fetch
python -m src.uwss.cli fetch --db data/uwss.sqlite --outdir data/files --limit 20 --config config/config.yaml --log-json

# 5) Extract
python -m src.uwss.cli extract-full-text --db data/uwss.sqlite --content-dir data/content --limit 20

# 6) Export
python -m src.uwss.cli export --db data/uwss.sqlite --out data/export/run_latest.jsonl --require-match --log-json
```

Tips:
- Safe to run many times: dedupe (DOI/title/url_hash) and checkpoints for discover.
- To collect more, increase `--max` (discover) and `--limit` (fetch/extract).


### Appendix: Setup Postgres local (Windows)
1) Install
- Download and install PostgreSQL (EDB installer). Remember password for user `postgres` and the port (default 5432).
- Open Services (services.msc) and make sure the service "PostgreSQL …" is Running.

2) Basic config (optional)
- Config file is usually at: `C:\Program Files\PostgreSQL\<version>\data\postgresql.conf`
  - Make sure:
    - `port = 5432` (or your desired port)
    - `listen_addresses = 'localhost'`
- After changes, restart the "PostgreSQL …" service.

3) Create database `uwss`
- Option A: pgAdmin4
  - Open pgAdmin4 → Connect (user `postgres`, your password)
  - Right click "Databases" → Create → Database → Name: `uwss` → Save
- Option B: psql (if in PATH)
  ```powershell
  psql -U postgres -h localhost -p 5432 -c "CREATE DATABASE uwss;"
  ```

4) Python driver
```powershell
cd D:\uwss
.\.venv\Scripts\Activate  # if venv exists
pip install -r requirements.txt  # includes psycopg2-binary
```

5) Set DB URL for this session
```powershell
$env:UWSS_DB_URL = "postgresql+psycopg2://postgres:<your_password>@localhost:5432/uwss"
echo $env:UWSS_DB_URL
```

6) Test connect and create indexes
```powershell
python -m src.uwss.cli --db-url $env:UWSS_DB_URL db-create-indexes
```

7) Ready to run the pipeline (see Quick start above).

Common issues
- Cannot connect: check service is Running, port correct, password correct.
- Port conflict: change `port` in `postgresql.conf` and use that port in URL.
- Missing driver: make sure `psycopg2-binary` is installed (`requirements.txt`).

### 3) Data sources
- Semantic Scholar: academic search by AI2; API for papers, authors, citations; good for metadata and publisher links.
- Europe PMC: life sciences/biomedical; many open-access; stable cursor API.
- Crossref: DOI registry; broad metadata for titles/authors/journals/DOI links.
- arXiv: preprint repository; ATOM API; useful for open pre-publication versions.
- PubMed Central (PMC): NCBI open full-text; E-utilities; many direct PDF/HTML.
- DOAJ: open access journal directory; API returns bibjson and fulltext links.

### 4) Output example 
One line in `data/export/run_latest.jsonl`:
```json
{
  "id": 2,
  "source_url": "https://www.semanticscholar.org/paper/89b2...",
  "landing_url": "https://www.semanticscholar.org/paper/89b2...",
  "pdf_url": "https://ijcsm.springeropen.com/counter/pdf/10.1186/s40069-024-00680-1",
  "doi": "10.1186/s40069-024-00680-1",
  "title": "Transport Characteristics and Corrosion Behavior of UHPC...",
  "authors": "[\"Shamsad Ahmad\", ...]",
  "venue": "International Journal of Concrete Structures and Materials",
  "year": 2024,
  "relevance_score": 1.0,
  "status": "fetched",
  "pdf_path": "data\\files\\10_1186_s40069-024-00680-1_id2.pdf",
  "content_path": "data\\content\\doc_2.txt",
  "content_chars": 62271,
  "open_access": true,
  "license": "cc-by",
  "source": "semantic_scholar",
  "oa_status": "publisher",
  "topic": "reinforced concrete corrosion experiment, ..."
}
```

### 5) Run many times without duplicates
- `documents` is deduped by DOI/title/url_hash before insert.
- `IngestionState` stores checkpoints (offset/cursor/page) → use `--resume` in discover.
- `VisitedUrl` records fetched/resolved URLs.
- Fetch/Extract only fills `local_path`/`content_path` when missing (idempotent).

### 6) Why Postgres-first?
- Stable when data grows; easy snapshots (JSONL/CSV) and stats.
- Works both local and when deployed (Docker/cloud) without code change.

### 7) Database and data types
- DB: Postgres for ops/deploy; SQLite for local; via SQLAlchemy.
- Files: PDF/HTML and text stored on disk (`data/files/`, `data/content/`); DB stores paths only (`local_path`/`pdf_path`, `content_path`). This avoids huge DB size and slow I/O.

- `documents` table (main):
  - id: INTEGER (auto increment PK)
  - source_url, landing_url, pdf_url: VARCHAR(1000)
  - doi: VARCHAR(255)
  - title: VARCHAR(1000)
  - authors: TEXT (JSON string of author names)
  - venue: VARCHAR(255)
  - year: INTEGER; pub_date: VARCHAR(20)
  - abstract: TEXT
  - local_path (alias pdf_path), content_path: VARCHAR(1000)
  - content_chars, file_size, http_status: INTEGER
  - open_access: BOOLEAN; license: VARCHAR(255); oa_status: VARCHAR(50)
  - relevance_score: FLOAT; keywords_found: TEXT (JSON string list)
  - status: VARCHAR(40); source: VARCHAR(50)
  - mime_type: VARCHAR(100); text_excerpt: TEXT
  - fetched_at: DATETIME; checksum_sha256: VARCHAR(64)
  - url_hash_sha1: VARCHAR(40)
  - topic: VARCHAR(100)

- `ingestion_state` (API checkpoints):
  - id (INTEGER PK), source (VARCHAR(50)), checkpoint_key (VARCHAR(100)),
    checkpoint_value (VARCHAR(1000)), updated_at (DATETIME)

- `visited_urls` (seen URLs):
  - url (VARCHAR(1000) PK), first_seen (DATETIME), last_seen (DATETIME), status (VARCHAR(50))

- Export: JSONL/CSV from Postgres. JSONL = one JSON record per line with full fields.

### 8) Simple configuration
- `config/config.yaml` has `domain_keywords`, `negative_keywords`, `contact_email`, rate limits, etc.
- You can override keywords with `--keywords-file`.

### 9) Quality and observability
- Negative keywords remove off-topic items.
- JSON logs (`--log-json`) show progress and metrics.
- Indexes (doi, lower(title), url_hash_sha1) speed up queries/export.

### 10) Conclusion
- The system meets requirements: professional, maintainable, no duplicates across runs, full identification, easy export.
- Can extend: paid proxy (reduce 403), GROBID for PDF scan, more sources.

### Appendix: Example flow 
Assume the topic is “reinforced concrete deterioration” and a keyword is “chloride diffusion test”. The pipeline works like a chain:

1) Discover
- `discover-semanticscholar` calls the Semantic Scholar API with that keyword → returns a paper:
  - DOI = 10.1186/s40069-024-00680-1
  - Title = “Transport Characteristics and Corrosion Behavior of UHPC …”
  - Result URL = https://www.semanticscholar.org/paper/…
- I insert into `documents` (Postgres): title, doi, source_url, year, venue…
- Dedup: if DOI already exists, no new row is created.

2) Score
- The scorer tokenizes title/abstract; the phrase “chloride diffusion” hits in title → high score.
- `keywords_found` keeps matched phrases (for explain).
- If negative words (e.g., “neural network”) appear, a penalty lowers the score.

3) Unpaywall enrich
- Query Unpaywall by DOI → get `is_oa = true`, `url_for_pdf`.
- Update `pdf_url`, and `license`/`oa_status` if present.

4) Resolve publisher
- If `source_url` is an aggregator (like S2), follow “View via Publisher”.
- On the publisher page, look for `citation_pdf_url`, rel=alternate PDF link, or *.pdf anchors → update `pdf_url`/`landing_url` if better.

5) Download
- Prefer `pdf_url`; otherwise try `source_url`/`landing_url`.
- Save the file as `data/files/..._id{document_id}.pdf`; update `local_path`, `mime_type`, `file_size`, `checksum_sha256`.
- `visited_urls` saves seen URLs (first_seen/last_seen/status).

6) Extract
- Read the local PDF/HTML, convert to text, save to `data/content/doc_{id}.txt`.
- Update `content_path`, `content_chars` in DB.

7) Export
- Read from Postgres, apply filters (e.g., `--require-match`), write one JSON per line to `data/export/*.jsonl`.
- Each line has full identification fields: `id, doi, title, authors, year, source_url, landing_url, pdf_url, pdf_path(local_path), content_path, open_access, license, oa_status, relevance_score, topic,…`

8) Safe to run again
- Discover won’t create duplicates due to DOI/title/url_hash checks.
- Fetch/Extract only fill missing `local_path`/`content_path`.
- `ingestion_state` lets you `--resume` and continue from the next page.

### References and inspirations
- [Semantic Scholar API](https://api.semanticscholar.org/api-docs/graph)
- [Europe PMC REST API](https://europepmc.org/RestfulWebService)
- [Crossref REST API](https://api.crossref.org/)
- [arXiv API](https://info.arxiv.org/help/api/index.html)
- [NCBI E-utilities (PMC/PubMed)](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [DOAJ API](https://doaj.org/api/v2/docs)
- [Unpaywall API](https://unpaywall.org/products/api)
- [Scrapy Docs](https://docs.scrapy.org/en/latest/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Requests Docs](https://requests.readthedocs.io/en/latest/)

 -->
