import uuid

from fastapi import APIRouter, HTTPException
from langgraph.types import Command

from app.graph.runtime import get_graph
from app.schemas.brief import (
    BriefRequest,
    BriefResponse,
    BriefStateModel,
    ResumeRequest,
)

router = APIRouter(prefix="/research", tags=["research"])


def _extract_interrupt(result: dict) -> dict | None:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    if hasattr(first, "value"):
        return first.value
    if isinstance(first, dict):
        return first.get("value", first)
    return {"raw": str(first)}


def _format(run_id: str, result: dict) -> BriefResponse:
    payload = _extract_interrupt(result)
    state_dict = {k: v for k, v in result.items() if not k.startswith("__")}
    return BriefResponse(
        run_id=run_id,
        status="awaiting_review" if payload is not None else "completed",
        state=BriefStateModel(**state_dict),
        interrupt=payload,
    )


@router.post("/brief", response_model=BriefResponse)
async def run_brief(request: BriefRequest):
    """Start a new brief. Returns the draft and an interrupt if human approval is needed."""
    run_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": run_id}}
    graph = get_graph()

    result = await graph.ainvoke(
        {"topic": request.topic, "trace": []},
        config=config,
    )
    return _format(run_id, result)


@router.post("/brief/{run_id}/resume", response_model=BriefResponse)
async def resume_brief(run_id: str, request: ResumeRequest):
    """Resume a paused run with a human decision."""
    config = {"configurable": {"thread_id": run_id}}
    graph = get_graph()

    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="Run not found")
    if not snapshot.next:
        raise HTTPException(status_code=400, detail="Run is not awaiting review")

    payload = request.model_dump(exclude_none=True)
    result = await graph.ainvoke(Command(resume=payload), config=config)
    return _format(run_id, result)