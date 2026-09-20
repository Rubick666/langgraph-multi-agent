"""Runs a brief job in the background.

Uses asyncio.create_task, so a server restart mid-run will lose the task.
That's acceptable for this portfolio piece — in production you'd swap this
for a real worker (Celery, RQ, arq) or LangGraph Platform. The job table
still records the last known status, so a client polling after a restart
will see the run as stuck in 'running' and can decide to resubmit.
"""
import asyncio

from app.graph.runtime import get_graph
from app.jobs import registry


_background_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


def _has_interrupt(result: dict) -> bool:
    interrupts = result.get("__interrupt__")
    return bool(interrupts)


async def run_brief_job(run_id: str, topic: str, jobs_conn) -> None:
    """Execute the workflow and keep the jobs table in sync."""
    try:
        await registry.update_status(jobs_conn, run_id, "running")
        graph = get_graph()
        config = {"configurable": {"thread_id": run_id}}

        result = await graph.ainvoke(
            {"topic": topic, "trace": []},
            config=config,
        )

        if _has_interrupt(result):
            await registry.update_status(jobs_conn, run_id, "awaiting_review")
        else:
            await registry.update_status(jobs_conn, run_id, "completed")
    except Exception as e:
        await registry.update_status(
            jobs_conn, run_id, "failed", error=f"{type(e).__name__}: {e}"
        )


def spawn_brief_job(run_id: str, topic: str, jobs_conn) -> None:
    """Fire-and-forget: kick off the runner in the background."""
    _spawn(run_brief_job(run_id, topic, jobs_conn))