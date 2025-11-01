## Phase 3 Runbook (arXiv‑first)

### Goals
- Stable OAI‑PMH harvest, canonical PDF fetch (pinned→latest), GROBID parse (optional), precision export, and monitoring.

### Clean run (recommended)
```
python -m src.uwss.cli arxiv-harvest-oai --db data/uwss_clean.sqlite --from 2024-01-01 --until 2025-11-01 --max 200 --resume --metrics-out data/runs_clean/arxiv_h.json --log-json
python -m src.uwss.cli arxiv-fetch-pdf   --db data/uwss_clean.sqlite --outdir data/files_clean --limit 200 --metrics-out data/runs_clean/arxiv_p.json --log-json
```

### Optional parse (GROBID)
```
docker run -d --name grobid -p 8070:8070 lfoppiano/grobid:0.8.0
python -m src.uwss.cli arxiv-parse-grobid --db data/uwss_clean.sqlite --content-dir data/content_clean --limit 50 --grobid-url http://localhost:8070 --log-json
```

### Score and export (precision)
```
python -m src.uwss.cli score-keywords --db data/uwss_clean.sqlite --config config/config.yaml --min 0.0
python -m src.uwss.cli export --db data/uwss_clean.sqlite --out data/export_clean/arxiv.jsonl --require-match --skip-missing-core --year-min 1995 --log-json
```

### Monitoring & summaries
```
python -m src.uwss.cli recent-downloads --db data/uwss_clean.sqlite --hours 2 --limit 20 --source arxiv --json-out data/runs_clean/recent.json
python -m src.uwss.cli runs-summary     --dir data/runs_clean --limit 100 --out data/runs_clean/summary.json
python -m src.uwss.cli validate         --db data/uwss_clean.sqlite --json-out data/export_clean/validation.json
python -m src.uwss.cli stats            --db data/uwss_clean.sqlite --json-out data/export_clean/stats.json
```

### QA checklist (quick)
- Spot‑check 20 records trong `data/export_clean/arxiv.jsonl` (đúng chủ đề? title/abstract/doi/year?).
- Mở vài PDF từ `data/files_clean/` (dựa recent.json) để đối chiếu nội dung.
- Kiểm duplicate: dùng `validate` và (tuỳ chọn) `dedupe-resolve` / `dedupe-resolve-fuzzy`.
- Quan sát metrics fetch (tỉ lệ ok/404/403/5xx, p95 latency) từ `data/runs_clean/*.json` và `summary.json`.

### Notes
- Fetch ưu tiên URL version‑pinned (`.../IDvN.pdf`) rồi fallback latest (`.../ID.pdf`).
- `--require-match` giúp lọc theo domain keywords trong `config/config.yaml`.
- Có thể chạy “hai tầng”: export trước → chỉ fetch những bản đã qua lọc.

