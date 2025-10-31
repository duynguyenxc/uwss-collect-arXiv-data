from __future__ import annotations

import os
import time
import random
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import requests

from ..store import Document, VisitedUrl


def _safe_filename(base: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in base)[:128]


def _guess_arxiv_id(landing_url: Optional[str], pdf_url: Optional[str]) -> Optional[str]:
    for u in (pdf_url, landing_url):
        if not u:
            continue
        if "/pdf/" in u:
            # https://arxiv.org/pdf/xxxx.pdf
            part = u.split("/pdf/")[-1]
            return part.replace(".pdf", "")
        if "/abs/" in u:
            part = u.split("/abs/")[-1]
            return part
    return None


def fetch_arxiv_pdfs(
    session,
    out_dir: Path,
    limit: int = 50,
    contact_email: Optional[str] = None,
    throttle_sec: float = 1.0,
    jitter_sec: float = 0.5,
) -> Dict[str, Any]:
    """Download canonical arXiv PDFs for arXiv-sourced documents.

    - Respects polite UA and pacing.
    - Writes to out_dir; updates Document.local_path, http_status, file_size, fetched_at, mime_type, status.
    - Records VisitedUrl for provenance.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": f"uwss/0.1 (+pdf; {contact_email or 'contact@unknown'})",
        "Accept": "application/pdf, */*;q=0.8",
        "Connection": "close",
    }

    q = (
        session.query(Document)
        .filter(Document.source == "arxiv")
        .filter(Document.pdf_url != None)
        .filter((Document.local_path == None) | (Document.local_path == ""))
        .limit(limit)
    )
    rows = q.all()

    downloaded = 0
    failed = 0
    not_found_404 = 0
    forbidden_403 = 0
    errors_5xx = 0
    timeouts = 0
    retries_total = 0
    bytes_downloaded = 0
    latencies_ms: list[int] = []
    for d in rows:
        url = d.pdf_url
        if not url:
            continue
        # build filename
        arxiv_id = _guess_arxiv_id(d.landing_url, d.pdf_url) or hashlib.sha1((d.pdf_url or d.source_url or str(d.id)).encode("utf-8")).hexdigest()[:12]
        fname = _safe_filename(f"arxiv_{arxiv_id}.pdf")
        fpath = out_dir / fname
        meta_path = out_dir / (fname.replace(".pdf", ".meta.json"))
        # skip if already exists
        if fpath.exists():
            d.local_path = str(fpath)
            d.status = "fetched"
            d.fetched_at = datetime.utcnow()
            session.add(d)
            downloaded += 1
            continue
        # retry for transient errors
        attempt = 0
        max_retries = 3
        start_ts = time.time()
        while True:
            attempt += 1
            try:
                resp = requests.get(url, headers=headers, timeout=60, stream=True)
                d.http_status = resp.status_code
                ct = (resp.headers.get("Content-Type") or "").lower()
                if resp.status_code == 200 and ct.startswith("application/pdf"):
                    tmp_path = fpath.with_suffix(".part")
                    sha = hashlib.sha256()
                    total_bytes = 0
                    with open(tmp_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=1024 * 64):
                            if chunk:
                                f.write(chunk)
                                sha.update(chunk)
                                total_bytes += len(chunk)
                    os.replace(tmp_path, fpath)
                    checksum = sha.hexdigest()
                    d.local_path = str(fpath)
                    d.status = "fetched"
                    d.mime_type = resp.headers.get("Content-Type")
                    d.file_size = total_bytes
                    d.checksum_sha256 = checksum
                    d.fetched_at = datetime.utcnow()
                    downloaded += 1
                    bytes_downloaded += total_bytes
                    # write meta.json
                    try:
                        import json
                        meta = {
                            "url_used": url,
                            "status": resp.status_code,
                            "etag": resp.headers.get("ETag"),
                            "last_modified": resp.headers.get("Last-Modified"),
                            "content_type": resp.headers.get("Content-Type"),
                            "sha256": checksum,
                            "file_size": total_bytes,
                            "fetched_at": d.fetched_at.isoformat() + "Z",
                        }
                        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                    except Exception:
                        pass
                else:
                    failed += 1
                    if resp.status_code == 404:
                        not_found_404 += 1
                    elif resp.status_code == 403:
                        forbidden_403 += 1
                    elif 500 <= resp.status_code < 600:
                        errors_5xx += 1
                    d.status = "fetch_failed"
                # visited url
                try:
                    vu = VisitedUrl(url=url, first_seen=datetime.utcnow(), last_seen=datetime.utcnow(), status=str(resp.status_code))
                    session.merge(vu)
                except Exception:
                    pass
            except requests.Timeout:
                timeouts += 1
                failed += 1
                d.status = "fetch_failed"
            except Exception:
                failed += 1
                d.status = "fetch_failed"
            finally:
                latency_ms = int((time.time() - start_ts) * 1000)
                latencies_ms.append(latency_ms)
                session.add(d)
                session.commit()
            if d.status == "fetched":
                break
            if attempt <= max_retries and (d.http_status in (429,) or (d.http_status and 500 <= d.http_status < 600)):
                retries_total += 1
                time.sleep(throttle_sec + random.random() * jitter_sec)
                continue
            break
        # pacing per attempt group
        time.sleep(throttle_sec + random.random() * jitter_sec)

    lat_sorted = sorted(latencies_ms)
    def pct(p: float):
        if not lat_sorted:
            return None
        k = int(max(0, min(len(lat_sorted) - 1, round(p * (len(lat_sorted) - 1)))))
        return lat_sorted[k]
    return {
        "attempted": len(rows),
        "downloaded": downloaded,
        "failed": failed,
        "not_found_404": not_found_404,
        "forbidden_403": forbidden_403,
        "errors_5xx": errors_5xx,
        "timeouts": timeouts,
        "retries": retries_total,
        "bytes_downloaded": bytes_downloaded,
        "latency_ms": {"p50": pct(0.5), "p95": pct(0.95), "max": (max(lat_sorted) if lat_sorted else None)},
    }


