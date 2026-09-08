from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    douyin_cookie: str = os.getenv("DOUYIN_COOKIE", "").strip()
    compat_token: str = os.getenv("COMPAT_TOKEN", "").strip()
    http_proxy: str = os.getenv("HTTP_PROXY", "").strip()
    https_proxy: str = os.getenv("HTTPS_PROXY", "").strip()
    default_quality: str = os.getenv("DEFAULT_QUALITY", "best").strip().lower()
    default_codec: str = os.getenv("DEFAULT_CODEC", "auto").strip().lower()
    docs_enabled: bool = _bool("DOCS_ENABLED", True)


settings = Settings()
