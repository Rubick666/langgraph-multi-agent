import uuid

from fastapi import APIRouter

from app.graph.runtime import get_graph
from app.schemas.brief import BriefRequest, BriefResponse, BriefStateModel

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/brief", response_model=BriefResponse)
async def run_brief(request: BriefRequest):
    """Run the full supervisor + agents pipeline synchronously."""
    run_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": run_id}}
    graph = get_graph()

    result = await graph.ainvoke(
        {"topic": request.topic, "trace": []},
        config=config,
    )

    state_dict = {k: v for k, v in result.items() if not k.startswith("__")}
    return BriefResponse(
        run_id=run_id,
        status="completed",
        state=BriefStateModel(**state_dict),
    )