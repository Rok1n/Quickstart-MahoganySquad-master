from __future__ import annotations

import re
from urllib.parse import urlparse

from fastapi import Header, HTTPException, status

from .settings import settings

ALLOWED_HOSTS = {
    "douyin.com",
    "www.douyin.com",
    "v.douyin.com",
    "iesdouyin.com",
    "www.iesdouyin.com",
}
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        if settings.allow_insecure_no_api_key:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API_KEY is not configured",
        )
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def extract_and_validate_douyin_url(text: str) -> str:
    match = URL_RE.search(text.strip())
    if not match:
        raise HTTPException(status_code=400, detail="No URL found")
    url = match.group(0).rstrip(".,;!?)】）]}>'\"")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or host not in ALLOWED_HOSTS:
        raise HTTPException(status_code=400, detail="Only Douyin URLs are accepted")
    return url
