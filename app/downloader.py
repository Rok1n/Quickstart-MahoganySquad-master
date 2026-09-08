from __future__ import annotations

import asyncio
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from .quality import Variant, extract_variants, select_variant
from .settings import settings
from .store import update_task
from .upstream import kernel

_sem = asyncio.Semaphore(settings.max_concurrent_downloads)


def _safe(text: str, fallback: str = "untitled", limit: int = 80) -> str:
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", (text or "").strip())
    text = re.sub(r"\s+", " ", text).strip(" ._")
    return (text or fallback)[:limit]


def _author(detail: dict[str, Any]) -> str:
    author = detail.get("author") or {}
    return _safe(str(author.get("nickname") or author.get("unique_id") or "unknown-author"))


def _target_path(detail: dict[str, Any], aweme_id: str, variant: Variant) -> Path:
    created = int(detail.get("create_time") or 0)
    day = datetime.fromtimestamp(created).strftime("%Y-%m-%d") if created else datetime.now().strftime("%Y-%m-%d")
    desc = _safe(str(detail.get("desc") or "douyin"), "douyin", 72)
    folder = settings.download_dir / _author(detail) / day
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{desc}_{aweme_id}_{variant.label}_{variant.codec}.mp4"
    return folder / _safe(name, f"{aweme_id}.mp4", 180)


def _disk_guard() -> None:
    settings.download_dir.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(settings.download_dir).free
    if free < settings.min_free_disk_gb * 1024**3:
        raise RuntimeError(f"Free disk space is below MIN_FREE_DISK_GB={settings.min_free_disk_gb}")


async def run_download(task_id: str, raw_url: str, quality: str, codec: str) -> None:
    async with _sem:
        partial: Path | None = None
        try:
            _disk_guard()
            await update_task(task_id, status="downloading", error=None)
            aweme_id, detail = await kernel.parse(raw_url)
            if detail.get("aweme_type") in {2, 68} or detail.get("images"):
                raise RuntimeError("This first release supports Douyin video posts only; image posts are not downloaded yet")
            variants = extract_variants(detail)
            selected = select_variant(variants, quality, codec)
            target = _target_path(detail, aweme_id, selected)
            partial = target.with_suffix(target.suffix + ".part")

            metadata = {
                "desc": detail.get("desc"),
                "author": detail.get("author"),
                "create_time": detail.get("create_time"),
                "selected": selected.public(),
                "variants": [v.public() for v in variants],
            }
            await update_task(
                task_id,
                aweme_id=aweme_id,
                file_path=str(target),
                metadata_json=metadata,
            )

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Referer": "https://www.douyin.com/",
            }
            timeout = httpx.Timeout(settings.request_timeout_seconds, read=None)
            async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers=headers) as client:
                async with client.stream("GET", selected.url) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("content-length") or selected.data_size or 0)
                    limit = settings.max_download_size_gb * 1024**3
                    if total and total > limit:
                        raise RuntimeError("Remote file exceeds MAX_DOWNLOAD_SIZE_GB")
                    await update_task(task_id, bytes_total=total)
                    done = 0
                    last_report = 0
                    with open(partial, "wb") as f:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            if not chunk:
                                continue
                            f.write(chunk)
                            done += len(chunk)
                            if done > limit:
                                raise RuntimeError("Downloaded data exceeded MAX_DOWNLOAD_SIZE_GB")
                            if done - last_report >= 8 * 1024 * 1024:
                                await update_task(task_id, bytes_done=done)
                                last_report = done
                    await update_task(task_id, bytes_done=done, bytes_total=total or done)

            partial.replace(target)
            await update_task(task_id, status="completed", file_path=str(target))
        except Exception as exc:
            if partial and partial.exists():
                partial.unlink(missing_ok=True)
            await update_task(task_id, status="failed", error=str(exc)[:1000])
