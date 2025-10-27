## Universal Web-Scraping System (UWSS) — Summary Report

### 1) Mục tiêu dự án (ngắn gọn)
- Thu thập (discover) tài liệu học thuật liên quan đến chủ đề “reinforced concrete deterioration” từ các nguồn công khai (Semantic Scholar, Europe PMC, Crossref, arXiv, PMC, DOAJ).
- Tự động tải file mở (PDF/HTML) khi có, trích xuất nội dung, và xuất kết quả dạng JSONL với đầy đủ trường nhận dạng (ID, DOI, Title, Authors, Year, Source URL, Landing URL, PDF URL, PDF Path, Content Path, Open Access, License…).
- Hệ thống có khả năng chạy lặp nhiều lần mà không bị trùng lặp nhờ deduplication và checkpoint.

### 2) Cách hệ thống vận hành (end-to-end)
1. Discover (tìm ứng viên qua API):
   - Nguồn: Semantic Scholar (chính), Europe PMC, Crossref, arXiv, PMC, DOAJ.
   - Đọc keyword từ `config/config.yaml` → gọi API → ghi vào PostgreSQL bảng `documents`.
   - Tránh trùng: kiểm DOI → title → url_hash.
2. Score (điểm phù hợp theo keyword):
   - Dựa trên token/bigram của tiêu đề/tóm tắt; title nặng hơn.
   - Hỗ trợ negative keywords (trong config) để loại nhiễu (AI/ML khi không liên quan).
3. Fetch (tải file) + Resolve (nâng chất link):
   - Enrich Unpaywall: lấy OA, license, best PDF/landing.
   - Resolve publisher: theo link “View via Publisher”, nhận diện PDF qua meta/link.
   - Download: ghi file vào `data/files/`, cập nhật `local_path`, checksum, mime type…
4. Extract (trích xuất nội dung):
   - Đọc PDF/HTML, lưu text vào `data/content/`, cập nhật `content_path`, `content_chars`.
5. Export (xuất dữ liệu):
   - JSONL/CSV từ Postgres theo bộ lọc (ví dụ `--require-match`), có thể thêm negative keywords.

Tất cả lệnh chạy qua `src/uwss/cli.py`, ví dụ:
```powershell
# Chuẩn bị (PowerShell)
$env:UWSS_DB_URL = "postgresql+psycopg2://postgres:123456@localhost:5432/uwss"
python -m src.uwss.cli --db-url $env:UWSS_DB_URL db-create-indexes
python -m src.uwss.cli --db-url $env:UWSS_DB_URL discover-semanticscholar --config config/config.yaml --max 50 --cache-ttl-sec 86400 --log-json
python -m src.uwss.cli --db-url $env:UWSS_DB_URL score-keywords --config config/config.yaml
python -m src.uwss.cli --db-url $env:UWSS_DB_URL fetch --limit 20 --config config/config.yaml --log-json
python -m src.uwss.cli --db-url $env:UWSS_DB_URL extract-full-text --content-dir data/content --limit 20
python -m src.uwss.cli --db-url $env:UWSS_DB_URL export --out data/export/run_latest.jsonl --require-match --log-json
```

### 3) Dữ liệu xuất ra (ví dụ rút gọn)
Một dòng trong `data/export/run_latest.jsonl`:
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

### 4) Tránh trùng lặp và chạy nhiều lần
- Bảng `documents` có kiểm tra DOI/title/url_hash trước khi chèn → tránh lặp.
- `IngestionState` ghi checkpoint (offset/cursor/page) → lệnh discover có `--resume`.
- `VisitedUrl` ghi URL đã tải/resolve → giảm gọi lại URL cũ.
- Fetch/Extract chỉ điền `local_path`/`content_path` nếu còn thiếu → idempotent.

### 5) Tại sao Postgres-first?
- Ổn định khi dữ liệu tăng; dễ xuất ảnh chụp (JSONL/CSV) và thống kê.
- Dùng được cả local và khi deploy (Docker/cloud) mà không đổi code.

### 6) Giao diện cấu hình đơn giản
- `config/config.yaml` chứa `domain_keywords`, `negative_keywords`, `contact_email`, giới hạn tốc độ, v.v.
- Có thể override keyword theo lần chạy bằng `--keywords-file`.

### 7) Chất lượng và quan sát
- Negative keywords giúp loại bớt kết quả lệch chủ đề.
- JSON logs (`--log-json`) hiển thị tiến độ/metrics để theo dõi.
- Index trên PG (doi, lower(title), url_hash_sha1) tăng tốc tra cứu/export.

### 8) Kết luận
- Hệ thống đáp ứng yêu cầu: chuyên nghiệp, có thể bảo trì, chạy nhiều lần không trùng, dữ liệu có nhận dạng đầy đủ, export dễ tích hợp.
- Có thể mở rộng: proxy thương mại (giảm 403), GROBID cho PDF scan, thêm nguồn API.


