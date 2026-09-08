from __future__ import annotations

import hmac
import re
from urllib.parse import urlparse

from fastapi import HTTPException, status

from .settings import settings

ALLOWED_HOSTS = {
    "douyin.com",
    "www.douyin.com",
    "v.douyin.com",
    "iesdouyin.com",
    "www.iesdouyin.com",
}
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


def verify_compat_token(token: str | None) -> None:
    """If COMPAT_TOKEN is blank the endpoint is public; otherwise a matching query token is required."""
    if not settings.compat_token:
        return
    if not token or not hmac.compare_digest(token, settings.compat_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


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
