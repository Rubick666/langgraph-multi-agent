from typing import Optional

from pydantic import BaseModel, Field


class BriefRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200)


class ResumeRequest(BaseModel):
    action: str = Field(..., description="approve | reject")
    note: Optional[str] = Field(None, max_length=500)


class JobAccepted(BaseModel):
    run_id: str
    status: str  # always "pending" for a fresh submission
    message: str = "Job accepted. Poll /research/brief/{run_id}/status."


class JobStatusResponse(BaseModel):
    run_id: str
    topic: Optional[str] = None
    status: str
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BriefStateModel(BaseModel):
    topic: Optional[str] = None
    wikipedia_summary: Optional[str] = None
    wikipedia_url: Optional[str] = None
    news_headlines: list[dict] = Field(default_factory=list)
    fact_check_notes: list[dict] = Field(default_factory=list)
    draft_brief: Optional[str] = None
    final_brief: Optional[str] = None
    human_action: Optional[str] = None
    human_note: Optional[str] = None
    errors: list[dict] = Field(default_factory=list)
    trace: list[dict] = Field(default_factory=list)


class BriefResponse(BaseModel):
    run_id: str
    status: str  # awaiting_review | completed | failed
    state: BriefStateModel
    interrupt: Optional[dict] = None
    error: Optional[str] = None