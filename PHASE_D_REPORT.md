## Phase D — Resolver & downloader robustness

### 1) Mục tiêu và tác dụng
- Tăng tỉ lệ tìm được PDF/landing hợp lệ (publisher resolver tốt hơn).
- Tải file ổn định hơn, nhận diện PDF qua Content-Type/Disposition.
- Chuẩn bị nền tảng cho Phase E (UA rotation/proxy) bằng biến môi trường.

### 2) Đã làm gì trong Phase D
- resolve_publisher_links:
  - Xử lý meta-refresh để theo chuỗi chuyển hướng ẩn trong HTML.
  - Dùng User-Agent tùy biến (_pick_user_agent) và giữ throttle của Phase A.
  - Tiếp tục phát hiện PDF qua meta `citation_pdf_url`, link rel alternate PDF, và anchor chứa “pdf”.
- download_open_links:
  - Nhận diện PDF bằng `Content-Type`, đuôi `.pdf`, và `Content-Disposition`.
  - Bổ sung proxy optional qua env; User-Agent chọn ngẫu nhiên nếu có danh sách.

### 3) Cách vận hành
```bash
# Env (tùy chọn) cho UA/proxy
$env:UWSS_UA_LIST = "Mozilla/5.0 ...|Mozilla/5.0 (Macintosh) ..."
# hoặc dùng file:
# $env:UWSS_UA_FILE = "config/user_agents.txt"
$env:UWSS_PROXIES = "http://user:pass@host1:port|http://user:pass@host2:port"
# hoặc file:
# $env:UWSS_PROXY_FILE = "config/proxies.txt"

# Chạy fetch như thường lệ
python -m src.uwss.cli --db-url $env:UWSS_DB_URL fetch --limit 10 --config config/config.yaml --log-json
```

### 4) Kỹ thuật đã dùng
- Meta-refresh parse bằng BeautifulSoup + regex url=...
- Content-Disposition và Content-Type để đoán đuôi lưu file.
- UA/proxy lấy từ env hoặc file cấu hình; chọn ngẫu nhiên mỗi request.

### 5) File & Hàm quan trọng
- `src/uwss/crawl/__init__.py`
  - `_pick_user_agent`, `_pick_proxy`, `_apply_proxy`.
  - `resolve_publisher_links` và `download_open_links` (cải thiện như trên).

### 6) Tác động
- Tăng hit-rate PDF từ các trang trung gian.
- Giảm lỗi tải sai định dạng hoặc đặt tên file không đúng.
