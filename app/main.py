from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .downloader import run_download
from .quality import extract_variants, select_variant
from .security import extract_and_validate_douyin_url, require_api_key
from .settings import settings
from .store import create_task, get_task, init_db, list_tasks
from .upstream import kernel


class ParseRequest(BaseModel):
    url: str = Field(..., description="Douyin URL or share text containing a Douyin URL")
    quality: str = "best"
    codec: str = "auto"


class DownloadRequest(ParseRequest):
    pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.download_dir.mkdir(parents=True, exist_ok=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    await init_db()
    yield


app = FastAPI(
    title="Douyin NAS",
    version="0.1.0",
    description="fnOS-oriented Douyin best-quality parser and background downloader",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url=None,
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "cookie_configured": bool(settings.douyin_cookie),
        "api_key_configured": bool(settings.api_key),
        "download_dir": str(settings.download_dir),
    }


@app.post("/api/v1/parse", dependencies=[Depends(require_api_key)])
async def parse_video(body: ParseRequest) -> dict:
    url = extract_and_validate_douyin_url(body.url)
    aweme_id, detail = await kernel.parse(url)
    if detail.get("aweme_type") in {2, 68} or detail.get("images"):
        return {
            "aweme_id": aweme_id,
            "type": "image",
            "message": "Image post detected; video quality selection does not apply",
        }
    variants = extract_variants(detail)
    try:
        selected = select_variant(variants, body.quality, body.codec)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "aweme_id": aweme_id,
        "type": "video",
        "desc": detail.get("desc"),
        "author": detail.get("author"),
        "create_time": detail.get("create_time"),
        "selected": selected.public(),
        "variants": [v.public() for v in variants],
    }


@app.post("/api/v1/downloads", status_code=202, dependencies=[Depends(require_api_key)])
async def enqueue_download(body: DownloadRequest) -> dict:
    url = extract_and_validate_douyin_url(body.url)
    quality = (body.quality or settings.default_quality).lower()
    codec = (body.codec or settings.default_codec).lower()
    if codec not in {"auto", "h264", "h265"}:
        raise HTTPException(status_code=400, detail="codec must be auto, h264, or h265")
    task_id = uuid.uuid4().hex
    await create_task(task_id, url, quality, codec)
    asyncio.create_task(run_download(task_id, url, quality, codec))
    return {"task_id": task_id, "status": "queued"}


@app.get("/api/v1/downloads", dependencies=[Depends(require_api_key)])
async def downloads(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    return {"items": await list_tasks(limit)}


@app.get("/api/v1/downloads/{task_id}", dependencies=[Depends(require_api_key)])
async def download_status(task_id: str) -> dict:
    task = await get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    total = task.get("bytes_total") or 0
    done = task.get("bytes_done") or 0
    task["progress"] = round(done * 100 / total, 2) if total else None
    return task
