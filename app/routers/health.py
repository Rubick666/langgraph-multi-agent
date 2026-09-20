from fastapi import APIRouter

from app.core.llm import llm

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    llm_ok = False
    try:
        resp = await llm.ainvoke("ping")
        llm_ok = bool(resp.content)
    except Exception:
        pass
    return {"status": "ok", "llm_reachable": llm_ok}