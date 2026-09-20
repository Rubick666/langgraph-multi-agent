import uuid

from fastapi import APIRouter, HTTPException, status
from langgraph.types import Command

from app.graph.runtime import get_graph, get_jobs_conn
from app.jobs import registry
from app.jobs.runner import spawn_brief_job
from app.schemas.brief import (
    BriefRequest,
    BriefResponse,
    BriefStateModel,
    JobAccepted,
    JobStatusResponse,
    ResumeRequest,
)

router = APIRouter(prefix="/research", tags=["research"])


# ---------------------------------------------------------------- helpers
def _extract_interrupt_from_result(result: dict) -> dict | None:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    if hasattr(first, "value"):
        return first.value
    if isinstance(first, dict):
        return first.get("value", first)
    return {"raw": str(first)}


def _extract_interrupt_from_snapshot(snapshot) -> dict | None:
    """Read the pending interrupt payload out of a state snapshot."""
    for task in snapshot.tasks or []:
        ints = getattr(task, "interrupts", None)
        if ints:
            first = ints[0]
            value = getattr(first, "value", None)
            if value is not None:
                return value
            return {"raw": str(first)}
    return None


def _format_result(run_id: str, result: dict, job_status: str, error=None) -> BriefResponse:
    payload = _extract_interrupt_from_result(result)
    state_dict = {k: v for k, v in result.items() if not k.startswith("__")}
    return BriefResponse(
        run_id=run_id,
        status=job_status,
        state=BriefStateModel(**state_dict),
        interrupt=payload,
        error=error,
    )


def _format_from_snapshot(run_id: str, snapshot, job: dict) -> BriefResponse:
    state_dict = dict(snapshot.values or {})
    payload = _extract_interrupt_from_snapshot(snapshot) if job["status"] == "awaiting_review" else None
    return BriefResponse(
        run_id=run_id,
        status=job["status"],
        state=BriefStateModel(**state_dict),
        interrupt=payload,
        error=job.get("error"),
    )


# ---------------------------------------------------------------- POST /brief
@router.post(
    "/brief",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_brief(request: BriefRequest):
    """Submit a research brief job. Returns immediately with a run_id."""
    run_id = str(uuid.uuid4())
    jobs_conn = get_jobs_conn()

    await registry.create_job(jobs_conn, run_id, request.topic)
    spawn_brief_job(run_id, request.topic, jobs_conn)

    return JobAccepted(run_id=run_id, status="pending")


# ---------------------------------------------------- GET /brief/{id}/status
@router.get("/brief/{run_id}/status", response_model=JobStatusResponse)
async def get_brief_status(run_id: str):
    job = await registry.get_job(get_jobs_conn(), run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return JobStatusResponse(**job)


# -------------------------------------------------------------- GET /brief/{id}
@router.get("/brief/{run_id}", response_model=BriefResponse)
async def get_brief(run_id: str):
    """Fetch the full state. Works for awaiting_review and completed runs.

    For pending/running runs, returns 202 with an empty state — clients should
    keep polling /status. For failed runs, returns the error and any partial state.
    """
    job = await registry.get_job(get_jobs_conn(), run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if job["status"] in {"pending", "running"}:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail=f"Run is still {job['status']}. Poll /research/brief/{run_id}/status.",
        )

    graph = get_graph()
    config = {"configurable": {"thread_id": run_id}}
    snapshot = await graph.aget_state(config)
    return _format_from_snapshot(run_id, snapshot, job)


# -------------------------------------------------- POST /brief/{id}/resume
@router.post("/brief/{run_id}/resume", response_model=BriefResponse)
async def resume_brief(run_id: str, request: ResumeRequest):
    """Resume a paused run with a human decision.

    Synchronous: the review node is fast (no network calls), so the client
    doesn't need to poll again.
    """
    jobs_conn = get_jobs_conn()
    job = await registry.get_job(jobs_conn, run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if job["status"] != "awaiting_review":
        raise HTTPException(
            status_code=400,
            detail=f"Run is not awaiting review (current status: {job['status']}).",
        )

    graph = get_graph()
    config = {"configurable": {"thread_id": run_id}}
    payload = request.model_dump(exclude_none=True)

    try:
        result = await graph.ainvoke(Command(resume=payload), config=config)
    except Exception as e:
        await registry.update_status(
            jobs_conn, run_id, "failed", error=f"{type(e).__name__}: {e}"
        )
        raise HTTPException(status_code=500, detail=f"Resume failed: {e}")

    if result.get("__interrupt__"):
        # Graph paused again (shouldn't happen in this graph, but be safe)
        await registry.update_status(jobs_conn, run_id, "awaiting_review")
        return _format_result(run_id, result, "awaiting_review")

    await registry.update_status(jobs_conn, run_id, "completed")
    return _format_result(run_id, result, "completed")