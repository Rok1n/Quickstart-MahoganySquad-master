from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from .settings import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    source_url TEXT NOT NULL,
    aweme_id TEXT,
    quality TEXT,
    codec TEXT,
    file_path TEXT,
    bytes_done INTEGER NOT NULL DEFAULT 0,
    bytes_total INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(SCHEMA)
        await db.execute(
            "UPDATE tasks SET status='interrupted', error='Service restarted during download', updated_at=? "
            "WHERE status IN ('queued','downloading')",
            (now(),),
        )
        await db.commit()


async def create_task(task_id: str, source_url: str, quality: str, codec: str) -> None:
    ts = now()
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "INSERT INTO tasks (id,created_at,updated_at,status,source_url,quality,codec) VALUES (?,?,?,?,?,?,?)",
            (task_id, ts, ts, "queued", source_url, quality, codec),
        )
        await db.commit()


async def update_task(task_id: str, **fields: Any) -> None:
    allowed = {"status", "aweme_id", "file_path", "bytes_done", "bytes_total", "error", "metadata_json"}
    data = {k: v for k, v in fields.items() if k in allowed}
    if "metadata_json" in data and not isinstance(data["metadata_json"], str):
        data["metadata_json"] = json.dumps(data["metadata_json"], ensure_ascii=False)
    data["updated_at"] = now()
    columns = ", ".join(f"{k}=?" for k in data)
    values = list(data.values()) + [task_id]
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(f"UPDATE tasks SET {columns} WHERE id=?", values)
        await db.commit()


async def get_task(task_id: str) -> dict[str, Any] | None:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute("SELECT * FROM tasks WHERE id=?", (task_id,))).fetchone()
    if not row:
        return None
    item = dict(row)
    try:
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
    except json.JSONDecodeError:
        item["metadata"] = {}
    return item


async def list_tasks(limit: int = 50) -> list[dict[str, Any]]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        except json.JSONDecodeError:
            item["metadata"] = {}
        result.append(item)
    return result
