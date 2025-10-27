## Phase A — PG-first stabilization and export parity

### 1) Mục tiêu và tác dụng
- Đưa Postgres thành “single source of truth” cho toàn bộ pipeline (discover → score → fetch → extract → export).
- Đảm bảo output (JSONL/CSV) giữ đầy đủ identification, tương đồng SQLite; có thể mở file PDF/Content từ đường dẫn lưu trong DB.
- Tăng hiệu năng và tính ổn định trên Postgres (index, clipping chiều dài cột, luồng chạy tiêu chuẩn).

### 2) Đã làm gì trong Phase A
- Bật Postgres cho các bước core:
  - score-keywords: thêm hỗ trợ `--db-url` và cập nhật `score_documents(...)` nhận DB URL.
  - fetch (Unpaywall enrich + download) và resolve publisher: thêm `--db-url` cho CLI; các hàm trong `crawl` nhận `db_url`.
  - extract-full-text / scrape-full-content: thêm `--db-url` cho CLI; các hàm trong `extract` nhận `db_url`.
  - export/stats/validate đã hỗ trợ PG sẵn (qua `--db-url`).
- Xử lý lỗi PG DataError (varchar): cắt ngắn `topic/venue/title` để tương thích schema (VARCHAR).
- Thêm lệnh tạo index: `db-create-indexes` (doi, lower(title), url_hash_sha1) giúp tra cứu/dedupe nhanh.
- Bổ sung lọc negative keywords ở `export` (tùy chọn `--negative-keywords-file`).
- Chuẩn hóa JSON logging (đã có ở discover/fetch/export/stats), giữ throttle/jitter và retry/backoff.

### 3) Cách vận hành (example)
Giả sử đã cài đặt driver và biến môi trường.

```bash
# 0) PowerShell: kích hoạt venv + thiết lập DB URL
cd D:\uwss
.venv\Scripts\Activate
$env:UWSS_DB_URL = "postgresql+psycopg2://postgres:123456@localhost:5432/uwss"

# 1) Tạo index cho Postgres
python -m src.uwss.cli --db-url $env:UWSS_DB_URL db-create-indexes

# 2) Discover vài bản ghi (ví dụ Europe PMC & Semantic Scholar)
python -m src.uwss.cli --db-url $env:UWSS_DB_URL discover-eupmc --config config/config.yaml --max 20 --cache-ttl-sec 86400 --log-json
python -m src.uwss.cli --db-url $env:UWSS_DB_URL discover-semanticscholar --config config/config.yaml --max 20 --cache-ttl-sec 86400 --log-json

# 3) Score để tạo relevance_score/keywords_found
python -m src.uwss.cli --db-url $env:UWSS_DB_URL score-keywords --config config/config.yaml

# 4) Enrich OA + Download file (PDF/HTML)
python -m src.uwss.cli --db-url $env:UWSS_DB_URL fetch --limit 10 --config config/config.yaml --log-json

# 5) Extract full text từ file local (ghi data/content, cập nhật content_path)
python -m src.uwss.cli --db-url $env:UWSS_DB_URL extract-full-text --content-dir data/content --limit 10

# 6) Export (ảnh chụp “latest”) – đầy đủ identification
python -m src.uwss.cli --db-url $env:UWSS_DB_URL \
  export --out data/export/final_latest.jsonl --require-match --log-json \
  --negative-keywords-file config/ai_keywords.txt
```

Kết quả:
- Bảng `documents` chứa metadata (doi, title, year, source_url/landing_url, pdf_url…), đường dẫn file `local_path` (alias `pdf_path` khi export), đường dẫn text `content_path`, kích thước/loại file, checksum, thời điểm fetch, v.v.
- File PDF/HTML lưu ở `data/files/`; full text ở `data/content/`. DB lưu đường dẫn nên mở file giống như SQLite.

### 4) Kỹ thuật đã dùng
- SQLAlchemy engine/session linh hoạt (SQLite/PG) thông qua `--db-url`.
- Retry/backoff + honor Retry-After (requests), per-host throttle + jitter (biến môi trường `UWSS_THROTTLE_SEC`, `UWSS_JITTER_SEC`).
- Structured JSON logging cho discover/fetch/export/stats.
- Index tối ưu hóa truy vấn (doi, lower(title), url_hash_sha1).
- Xử lý độ dài chuỗi an toàn (clipping) để tránh PG DataError.

### 5) File & Hàm quan trọng
- `src/uwss/cli.py`
  - `db-create-indexes`: tạo index hữu ích trên DB.
  - `score-keywords`, `fetch`, `download-open`, `extract-full-text`, `scrape-full-content` nhận `--db-url`.
  - `export`: thêm `--negative-keywords-file`; giữ đầy đủ identification khi ghi JSONL/CSV.
- `src/uwss/score/__init__.py`
  - `score_documents(db_path, keywords, min_score, db_url=None)`: chấm điểm trên PG hoặc SQLite.
- `src/uwss/crawl/__init__.py`
  - `resolve_publisher_links(..., db_url=None)`: theo “View via Publisher”, tìm PDF qua meta/link/anchor, urljoin liên kết tương đối.
  - `enrich_open_access_with_unpaywall(..., db_url=None)`: cập nhật OA/doi/license/pdf/landing_url.
  - `download_open_links(..., db_url=None)`: tải file vào `data/files/`, cập nhật provenance/checksum/url hash/VisitedUrl.
- `src/uwss/extract/__init__.py`
  - `extract_full_text(..., db_url=None)`: ghi `data/content/`, cập nhật `content_path`, `content_chars`.
  - `scrape_full_content(..., db_url=None)`: kéo HTML/PDF từ landing_url, trích nội dung.

### 6) Ví dụ nhỏ về hoạt động
- Sau discover + score, `export --require-match` chỉ xuất tài liệu có `keywords_found` (liên quan domain). Nếu chưa score sẽ ra 0; sau khi score sẽ có kết quả.
- Sau `fetch`, `local_path` (pdf_path) được điền; `extract-full-text` điền `content_path`/`content_chars`. Export hiển thị các trường này như ở SQLite.

### 7) Hướng dẫn chạy nhanh (tối thiểu)
```bash
python -m src.uwss.cli --db-url $env:UWSS_DB_URL db-create-indexes
python -m src.uwss.cli --db-url $env:UWSS_DB_URL discover-semanticscholar --config config/config.yaml --max 10 --cache-ttl-sec 86400
python -m src.uwss.cli --db-url $env:UWSS_DB_URL score-keywords --config config/config.yaml
python -m src.uwss.cli --db-url $env:UWSS_DB_URL fetch --limit 5 --config config/config.yaml
python -m src.uwss.cli --db-url $env:UWSS_DB_URL extract-full-text --content-dir data/content --limit 5
python -m src.uwss.cli --db-url $env:UWSS_DB_URL export --out data/export/final_latest.jsonl --require-match
```

### 8) Tác động
- Postgres trở thành nguồn dữ liệu thống nhất; output JSONL/CSV ổn định, giàu thông tin (identification đầy đủ).
- Tốc độ tốt hơn với index; ít lỗi do chuỗi dài nhờ clipping; quy trình chạy rõ ràng, dễ lặp lại.


