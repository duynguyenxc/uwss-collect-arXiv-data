## Phase C — Domain filtering with negative keywords

### 1) Mục tiêu và tác dụng
- Giảm tài liệu “lạc chủ đề” (ví dụ thiên về AI/ML) bằng cách áp dụng negative keywords trong bước scoring và export.
- Giữ kết quả gọn, sát domain, tăng chất lượng export cuối.

### 2) Đã làm gì trong Phase C
- Scoring:
  - Mở rộng `score_documents(..., negative_keywords=...)` để áp dụng penalty mạnh nếu xuất hiện từ khóa phủ định trong title/abstract (uni/bigram).
  - Thêm flag CLI `--negative-keywords-file` cho `score-keywords` để nạp danh sách phủ định từ file.
- Export:
  - Đã hỗ trợ `--negative-keywords-file` ở Phase A, dùng lọc substring trong title/abstract/text_excerpt.

### 3) Cách vận hành
```bash
# Ví dụ chạy scoring với negative keywords
python -m src.uwss.cli --db-url $env:UWSS_DB_URL \
  score-keywords --config config/config.yaml --negative-keywords-file config/ai_keywords.txt

# Export kèm lọc phủ định
python -m src.uwss.cli --db-url $env:UWSS_DB_URL \
  export --out data/export/final_latest.jsonl --require-match --negative-keywords-file config/ai_keywords.txt
```

Gợi ý nội dung `config/ai_keywords.txt` (mỗi dòng một cụm):
```
deep learning
neural network
transformer
computer vision
```

### 4) Kỹ thuật đã dùng
- Tokenize + bigram hóa cho cả từ khóa chính và phủ định; áp penalty theo số lượng hit phủ định.
- Giữ kiến trúc PG-first; không thay đổi schema.

### 5) File & Hàm quan trọng
- `src/uwss/score/__init__.py`
  - `score_documents(..., negative_keywords=...)`: áp dụng penalty; cập nhật relevance_score.
- `src/uwss/cli.py`
  - `score-keywords --negative-keywords-file`: đọc file, truyền danh sách vào scorer.
  - `export --negative-keywords-file`: lọc ở bước xuất.

### 6) Tác động
- Export cuối ít lẫn tài liệu AI/ML ngoài phạm vi domain.
- Không phá vỡ các pha khác; dễ bật/tắt qua file cấu hình.


