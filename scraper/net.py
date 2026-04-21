"""HTTP 层：带重试和编码处理的 GET。"""
from __future__ import annotations
import time
import logging
import requests
from config import USER_AGENT, REQUEST_TIMEOUT, MAX_RETRIES, DETAIL_ENCODING

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})


def get_text(url: str, encoding: str | None = None) -> str:
    """GET with retry. encoding=None 让 requests 猜（XML），显式指定则按该编码 decode。"""
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = _session.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            if encoding:
                return r.content.decode(encoding, errors="ignore")
            # requests 对 XML 可能猜错，优先信 XML declaration
            if r.content.startswith(b"<?xml"):
                r.encoding = "utf-8"
            return r.text
        except Exception as e:
            last_err = e
            wait = 0.5 * (2 ** (attempt - 1))
            log.warning("GET %s failed (attempt %d/%d): %s; sleep %.1fs",
                        url, attempt, MAX_RETRIES, e, wait)
            time.sleep(wait)
    raise RuntimeError(f"GET {url} failed after {MAX_RETRIES} attempts") from last_err


def get_detail(url: str) -> str:
    """抓单场比赛页（GBK）"""
    return get_text(url, encoding=DETAIL_ENCODING)
