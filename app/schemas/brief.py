from typing import Optional

from pydantic import BaseModel, Field


class BriefRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200)


class BriefStateModel(BaseModel):
    topic: Optional[str] = None
    wikipedia_summary: Optional[str] = None
    wikipedia_url: Optional[str] = None
    news_headlines: list[dict] = Field(default_factory=list)
    fact_check_notes: list[dict] = Field(default_factory=list)
    draft_brief: Optional[str] = None
    final_brief: Optional[str] = None
    errors: list[dict] = Field(default_factory=list)
    trace: list[dict] = Field(default_factory=list)


class BriefResponse(BaseModel):
    run_id: str
    status: str  # "completed" | "awaiting_review" | "running"
    state: BriefStateModel
    interrupt: Optional[dict] = None