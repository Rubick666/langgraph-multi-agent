"""Singleton graph + checkpointer + jobs connection.

All DB connections live here so the app has a single owner for them, and
routers can import `get_graph` / `get_jobs_conn` without circular imports.
"""
from typing import Optional

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.graph.workflow import build_graph
from app.jobs import registry

_graph = None
_saver: Optional[AsyncSqliteSaver] = None
_conn: Optional[aiosqlite.Connection] = None
_jobs_conn: Optional[aiosqlite.Connection] = None


async def init_runtime(database_path: str) -> None:
    global _graph, _saver, _conn, _jobs_conn
    if _graph is not None:
        return

    # Checkpointer connection
    _conn = await aiosqlite.connect(database_path)
    _saver = AsyncSqliteSaver(_conn)
    _graph = build_graph().compile(checkpointer=_saver)

    # Jobs connection (separate connection to avoid serialising writes with
    # the checkpointer's frequent small writes)
    _jobs_conn = await aiosqlite.connect(database_path)
    await registry.init_jobs_table(_jobs_conn)


async def close_runtime() -> None:
    global _graph, _saver, _conn, _jobs_conn
    if _conn is not None:
        await _conn.close()
    if _jobs_conn is not None:
        await _jobs_conn.close()
    _conn = None
    _jobs_conn = None
    _saver = None
    _graph = None


def get_graph():
    if _graph is None:
        raise RuntimeError("Graph not initialized — did startup run?")
    return _graph


def get_jobs_conn():
    if _jobs_conn is None:
        raise RuntimeError("Jobs connection not initialized — did startup run?")
    return _jobs_conn