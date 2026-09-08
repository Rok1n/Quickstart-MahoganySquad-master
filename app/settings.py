from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    api_key: str = os.getenv("API_KEY", "").strip()
    allow_insecure_no_api_key: bool = _bool("ALLOW_INSECURE_NO_API_KEY", False)
    douyin_cookie: str = os.getenv("DOUYIN_COOKIE", "").strip()
    http_proxy: str = os.getenv("HTTP_PROXY", "").strip()
    https_proxy: str = os.getenv("HTTPS_PROXY", "").strip()
    download_dir: Path = Path(os.getenv("DOWNLOAD_DIR", "/downloads"))
    data_dir: Path = Path(os.getenv("DATA_DIR", "/data"))
    default_quality: str = os.getenv("DEFAULT_QUALITY", "best").strip().lower()
    default_codec: str = os.getenv("DEFAULT_CODEC", "auto").strip().lower()
    max_concurrent_downloads: int = _int("MAX_CONCURRENT_DOWNLOADS", 2)
    max_download_size_gb: int = _int("MAX_DOWNLOAD_SIZE_GB", 20)
    min_free_disk_gb: int = _int("MIN_FREE_DISK_GB", 20)
    request_timeout_seconds: int = _int("REQUEST_TIMEOUT_SECONDS", 30)
    docs_enabled: bool = _bool("DOCS_ENABLED", True)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "douyin_nas.sqlite3"


settings = Settings()
