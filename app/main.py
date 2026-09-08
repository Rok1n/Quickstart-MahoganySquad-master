from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .quality import extract_variants, select_variant
from .security import extract_and_validate_douyin_url, verify_compat_token
from .settings import settings
from .upstream import kernel


class ParseRequest(BaseModel):
    url: str = Field(..., description="Douyin URL or share text containing a Douyin URL")
    quality: str = "best"
    codec: str = "auto"
    token: str | None = None


app = FastAPI(
    title="Douyin Original Parser",
    version="0.2.0",
    description="Parser-only Douyin API for fnOS and DYYY; returns direct media URLs and never stores media files.",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url=None,
)


def _first_http_url(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith("http"):
        return value
    if isinstance(value, dict):
        for key in ("url_list", "download_url_list"):
            urls = value.get(key)
            if isinstance(urls, list):
                for item in urls:
                    if isinstance(item, str) and item.startswith("http"):
                        return item
    return None


def _cover_url(detail: dict[str, Any]) -> str | None:
    video = detail.get("video") or {}
    for key in ("origin_cover", "cover", "dynamic_cover"):
        url = _first_http_url(video.get(key))
        if url:
            return url
    return None


def _music_url(detail: dict[str, Any]) -> str | None:
    music = detail.get("music") or {}
    for key in ("play_url", "play_url_uri"):
        url = _first_http_url(music.get(key))
        if url:
            return url
    return None


def _image_urls(detail: dict[str, Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for image in detail.get("images") or []:
        url = _first_http_url(image)
        if not url and isinstance(image, dict):
            for key in ("url", "display_image", "download_url"):
                url = _first_http_url(image.get(key))
                if url:
                    break
        if url and url not in seen:
            seen.add(url)
            result.append(url)
    return result


def _level(v: Any) -> str:
    bits = [v.label]
    if v.codec and v.codec != "unknown":
        bits.append(v.codec.upper())
    if v.bitrate:
        bits.append(f"{v.bitrate / 1_000_000:.1f}Mbps")
    return " / ".join(bits)


async def _parse_payload(raw_url: str, quality: str, codec: str) -> dict[str, Any]:
    url = extract_and_validate_douyin_url(raw_url)
    aweme_id, detail = await kernel.parse(url)

    common: dict[str, Any] = {
        "aweme_id": aweme_id,
        "desc": detail.get("desc") or "",
        "cover": _cover_url(detail),
        "music": _music_url(detail),
    }

    images = _image_urls(detail)
    if detail.get("aweme_type") in {2, 68} or images:
        common["images"] = images
        common["type"] = "image"
        return common

    variants = extract_variants(detail)
    selected = select_variant(variants, quality or settings.default_quality, codec or settings.default_codec)

    video_list = [
        {
            "url": v.url,
            "level": _level(v),
            "quality": v.label,
            "codec": v.codec,
            "width": v.width,
            "height": v.height,
            "bitrate": v.bitrate,
            "data_size": v.data_size,
        }
        for v in variants
    ]

    common.update(
        {
            "type": "video",
            "video_url": selected.url,
            "video": selected.url,
            "url": selected.url,
            "video_list": video_list,
            "selected_quality": selected.label,
            "selected_codec": selected.codec,
            "width": selected.width,
            "height": selected.height,
            "bitrate": selected.bitrate,
            "data_size": selected.data_size,
        }
    )
    return common


def _compat_error(code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=200, content={"code": code, "msg": message, "data": {}})


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "name": "Douyin Original Parser",
        "version": "0.2.0",
        "mode": "parser-only",
        "dyyy_endpoint": "/dy.php?url=",
        "token_supported": True,
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "parser-only",
        "cookie_configured": bool(settings.douyin_cookie),
        "compat_token_configured": bool(settings.compat_token),
        "default_quality": settings.default_quality,
        "default_codec": settings.default_codec,
    }


@app.get("/dy.php")
async def dyyy_compat(
    url: str | None = Query(default=None, description="Douyin share URL"),
    token: str | None = Query(default=None),
    quality: str = Query(default="best"),
    codec: str = Query(default="auto"),
):
    """DYYY-compatible GET endpoint, e.g. /dy.php?url=https://v.douyin.com/..."""
    try:
        verify_compat_token(token)
        if not url:
            return _compat_error(400, "缺少 url 参数")
        data = await _parse_payload(url, quality, codec)
        return {"code": 200, "msg": "success", "data": data}
    except HTTPException as exc:
        return _compat_error(exc.status_code, str(exc.detail))
    except ValueError as exc:
        return _compat_error(502, str(exc))
    except Exception as exc:
        return _compat_error(500, f"解析失败: {exc}")


@app.post("/api/v1/parse")
async def parse_api(body: ParseRequest) -> dict[str, Any]:
    """Debug/automation endpoint. Unlike /dy.php, HTTP errors are preserved."""
    verify_compat_token(body.token)
    data = await _parse_payload(body.url, body.quality, body.codec)
    return {"code": 200, "msg": "success", "data": data}
