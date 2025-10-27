## Phase E — User-Agent rotation & proxy plumbing

### 1) Mục tiêu và tác dụng
- Giảm nguy cơ bị chặn/throttle bằng cách xoay vòng User-Agent và hỗ trợ proxy.
- Không thay đổi logic nghiệp vụ; chỉ tăng tính ổn định khi truy cập nhiều nguồn.

### 2) Đã làm gì trong Phase E
- Thêm scaffolding UA/proxy trong `crawl` (requests flows):
  - Đọc UA từ `UWSS_UA_FILE` hoặc `UWSS_UA_LIST` (phân tách bằng `|`).
  - Đọc proxy từ `UWSS_PROXY_FILE` hoặc `UWSS_PROXIES` (phân tách bằng `|`).
  - Chọn ngẫu nhiên mỗi yêu cầu; có thể tắt bằng cách không set biến hoặc để file trống.
- Thêm file mẫu:
  - `config/user_agents.txt` (một số UA desktop phổ biến).
  - `config/proxies.txt` (hướng dẫn định dạng; để trống nếu không dùng).

### 3) Cách vận hành
```powershell
# Bật UA rotation (dùng file mẫu)
$env:UWSS_UA_FILE = "config/user_agents.txt"

# (Tuỳ chọn) Bật proxy từ file
$env:UWSS_PROXY_FILE = "config/proxies.txt"  # điền proxy thật nếu có

# Chạy fetch (UA/proxy sẽ tự áp dụng)
python -m src.uwss.cli --db-url $env:UWSS_DB_URL fetch --limit 10 --config config/config.yaml --log-json

# Hoặc dùng biến trực tiếp (không cần file)
$env:UWSS_UA_LIST = "Mozilla/5.0 ...|Mozilla/5.0 (Macintosh) ..."
$env:UWSS_PROXIES = "http://user:pass@host1:port|http://user:pass@host2:port"
```

### 4) Lưu ý
- Một số API (như Unpaywall/Crossref) yêu cầu `contact_email`; tiếp tục để trong `config.yaml` (đã hỗ trợ từ trước).
- Scrapy rotation/proxy sẽ bổ sung sau nếu cần (phase tiếp theo); hiện tại requests flows (fetch/resolve) đã nhận UA/proxy.

### 5) Tác động
- Linh hoạt hơn trong vận hành, giảm tỷ lệ lỗi do chặn nhẹ; không làm phức tạp hoá pipeline.


