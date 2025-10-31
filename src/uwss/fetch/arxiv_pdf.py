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
    for d in rows:
        url = d.pdf_url
        if not url:
            continue
        # build filename
        arxiv_id = _guess_arxiv_id(d.landing_url, d.pdf_url) or hashlib.sha1((d.pdf_url or d.source_url or str(d.id)).encode("utf-8")).hexdigest()[:12]
        fname = _safe_filename(f"arxiv_{arxiv_id}.pdf")
        fpath = out_dir / fname
        # skip if already exists
        if fpath.exists():
            d.local_path = str(fpath)
            d.status = "fetched"
            d.fetched_at = datetime.utcnow()
            session.add(d)
            downloaded += 1
            continue
        try:
            resp = requests.get(url, headers=headers, timeout=60, stream=True)
            d.http_status = resp.status_code
            if resp.status_code == 200 and (resp.headers.get("Content-Type", "").lower().startswith("application/pdf")):
                with open(fpath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            f.write(chunk)
                d.local_path = str(fpath)
                d.status = "fetched"
                d.mime_type = resp.headers.get("Content-Type")
                try:
                    d.file_size = fpath.stat().st_size
                except Exception:
                    d.file_size = None
                d.fetched_at = datetime.utcnow()
                downloaded += 1
            else:
                failed += 1
                d.status = "fetch_failed"
            # record visited url
            try:
                vu = VisitedUrl(url=url, first_seen=datetime.utcnow(), last_seen=datetime.utcnow(), status=str(resp.status_code))
                session.merge(vu)
            except Exception:
                pass
        except Exception:
            failed += 1
            d.status = "fetch_failed"
        finally:
            session.add(d)
            session.commit()
            # pacing
            time.sleep(throttle_sec + random.random() * jitter_sec)

    return {"downloaded": downloaded, "failed": failed, "attempted": len(rows)}


