"""Job lifecycle tracking.

The checkpointer stores *graph state*; this table stores *job state*.
They're separate concerns:
  - The checkpointer answers "what has the graph computed so far?"
  - The jobs table answers "is this run still going, paused, done, or broken?"
"""
from datetime import datetime, timezone

import aiosqlite


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    run_id     TEXT PRIMARY KEY,
    topic      TEXT NOT NULL,
    status     TEXT NOT NULL,
    error      TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

VALID_STATUSES = {"pending", "running", "awaiting_review", "completed", "failed"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_jobs_table(conn: aiosqlite.Connection) -> None:
    await conn.execute(CREATE_TABLE)
    await conn.commit()


async def create_job(conn: aiosqlite.Connection, run_id: str, topic: str) -> None:
    now = _now()
    await conn.execute(
        "INSERT INTO jobs (run_id, topic, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, topic, "pending", now, now),
    )
    await conn.commit()


async def update_status(
    conn: aiosqlite.Connection,
    run_id: str,
    status: str,
    error: str | None = None,
) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status}")
    await conn.execute(
        "UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE run_id = ?",
        (status, error, _now(), run_id),
    )
    await conn.commit()


async def get_job(conn: aiosqlite.Connection, run_id: str) -> dict | None:
    cur = await conn.execute(
        "SELECT run_id, topic, status, error, created_at, updated_at "
        "FROM jobs WHERE run_id = ?",
        (run_id,),
    )
    row = await cur.fetchone()
    await cur.close()
    if row is None:
        return None
    return {
        "run_id": row[0],
        "topic": row[1],
        "status": row[2],
        "error": row[3],
        "created_at": row[4],
        "updated_at": row[5],
    }