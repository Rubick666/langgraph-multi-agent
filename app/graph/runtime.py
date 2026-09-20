"""Holds the singleton graph and its SQLite checkpointer.

Lives outside main.py so routers can import `get_graph` without triggering a
circular import with main.
"""
from typing import Optional

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.graph.workflow import build_graph

_graph = None
_saver: Optional[AsyncSqliteSaver] = None
_conn: Optional[aiosqlite.Connection] = None


async def init_graph(database_path: str) -> None:
    global _graph, _saver, _conn
    if _graph is not None:
        return
    _conn = await aiosqlite.connect(database_path)
    _saver = AsyncSqliteSaver(_conn)
    _graph = build_graph().compile(checkpointer=_saver)


async def close_graph() -> None:
    global _graph, _saver, _conn
    if _conn is not None:
        await _conn.close()
    _conn = None
    _saver = None
    _graph = None


def get_graph():
    if _graph is None:
        raise RuntimeError("Graph not initialized — did startup run?")
    return _graph