from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .security import extract_and_validate_douyin_url
from .settings import settings

try:
    from crawlers.douyin.web import web_crawler as upstream_web_crawler
except Exception as exc:  # pragma: no cover
    upstream_web_crawler = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class DouyinKernel:
    def __init__(self) -> None:
        if upstream_web_crawler is None:
            raise RuntimeError(f"Unable to import upstream Douyin kernel: {_IMPORT_ERROR}")
        cfg = upstream_web_crawler.config["TokenManager"]["douyin"]
        if settings.douyin_cookie:
            cfg["headers"]["Cookie"] = settings.douyin_cookie
        if settings.http_proxy:
            cfg["proxies"]["http"] = settings.http_proxy
        if settings.https_proxy:
            cfg["proxies"]["https"] = settings.https_proxy
        self.crawler = upstream_web_crawler.DouyinWebCrawler()

    async def parse(self, raw_text: str) -> tuple[str, dict[str, Any]]:
        url = extract_and_validate_douyin_url(raw_text)
        try:
            aweme_id = await self.crawler.get_aweme_id(url)
            payload = await self.crawler.fetch_one_video(aweme_id)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Douyin parsing failed: {exc}") from exc
        detail = (payload or {}).get("aweme_detail")
        if not detail:
            raise HTTPException(
                status_code=502,
                detail="Douyin returned no aweme_detail; refresh DOUYIN_COOKIE or check network/proxy",
            )
        return str(aweme_id), detail


kernel = DouyinKernel()
