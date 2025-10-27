## Phase B — Import JSONL → Postgres with dedupe

### 1) Mục tiêu và tác dụng
- Hợp nhất các file JSONL/SQLite cũ vào Postgres, tránh duy trì “hai kho dữ liệu”.
- Dedupe an toàn theo DOI → title → url_hash_sha1, chỉ thêm mới khi chưa có; hoặc cập nhật có chọn lọc khi có thông tin bổ sung.

### 2) Đã làm gì trong Phase B
- Thêm lệnh CLI `import-jsonl`:
  - Đọc từng dòng JSONL, ánh xạ trường identification (doi, title, authors, venue, year, source_url, landing_url, pdf_url, local_path/pdf_path, content_path, content_chars, abstract, license, oa_status, relevance_score, keywords_found, topic...).
  - Dedupe chuỗi: ưu tiên DOI, sau đó title (so sánh chính xác), rồi `url_hash_sha1` (SHA1 của pdf_url/landing_url/source_url nếu không có sẵn).
  - Nếu bản ghi đã có: chỉ cập nhật cột đang trống; điểm số `relevance_score` sẽ lấy giá trị lớn hơn.
  - Hỗ trợ `--source-override` để ghi đè trường source khi nhập.
  - Hỗ trợ `--limit`, `--dry-run`, `--log-json`.

### 3) Cách vận hành
```bash
# Ví dụ nhập hợp nhất từ một file JSONL cũ
python -m src.uwss.cli --db-url $env:UWSS_DB_URL \
  import-jsonl --in data/export/final_results_clean.jsonl --limit 1000 --log-json

# Dry-run để xem thống kê trước khi ghi thật
python -m src.uwss.cli --db-url $env:UWSS_DB_URL \
  import-jsonl --in data/export/final_results_run2.jsonl --dry-run
```

Kết quả log JSON (ví dụ):
```json
{"uwss_event":"import_jsonl_done","inserted":120,"updated":45,"skipped":3,"file":"data/export/final_results_clean.jsonl"}
```

### 4) Kỹ thuật đã dùng
- SQLAlchemy session cho Postgres, đọc tuần tự từng dòng để tiết kiệm bộ nhớ.
- SHA1 url hash để nhận diện trùng khi thiếu DOI/title.
- Clipping chiều dài cột như Phase A để tránh PG DataError.

### 5) File & Hàm quan trọng
- `src/uwss/cli.py`
  - `import-jsonl`: parser + `_cmd_import_jsonl` cài đặt full logic nhập và dedupe.
- `src/uwss/store/models.py`
  - `Document.url_hash_sha1`: khóa phụ trợ cho dedupe khi thiếu DOI/title.

### 6) Ví dụ nhỏ về hoạt động
- Nếu một dòng JSONL có DOI trùng, nhưng thiếu `local_path` trong DB → lệnh sẽ cập nhật `local_path` từ JSONL.
- Nếu cả DOI và title đều không có, nhưng có `pdf_url` → lệnh sinh `url_hash_sha1` từ URL và dùng để nhận diện trùng.

### 7) Tác động
- Nhanh chóng hợp nhất kho dữ liệu cũ vào Postgres, từ đó chỉ vận hành duy nhất một DB.
- Giảm trùng lặp và sai lệch giữa các nguồn; export luôn lấy từ Postgres.


