from typing import Optional, TypedDict


class BriefState(TypedDict, total=False):
    """Shared state passed between the supervisor and every specialist agent."""
    # Input
    topic: str

    # Supervisor bookkeeping
    completed: list[str]           # names of agents that have already run
    next_action: Optional[str]     # supervisor's next decision

    # Agent outputs
    wikipedia_summary: Optional[str]
    wikipedia_url: Optional[str]
    news_headlines: list[dict]     # [{"title", "link", "published"}]

    fact_check_notes: list[dict]   # added in Step 2
    draft_brief: Optional[str]     # added in Step 2
    final_brief: Optional[str]     # added in Step 2

    # Failure tracking (agents push here instead of raising)
    errors: list[dict]

    # Human-in-the-loop (added in Step 2)
    human_action: Optional[str]
    human_note: Optional[str]

    # Observability
    trace: list[dict]