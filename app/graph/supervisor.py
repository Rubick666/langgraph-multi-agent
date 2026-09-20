"""Supervisor node — decides which specialist runs next.

The supervisor is the single point of coordination. Every specialist routes
back here, and the supervisor uses the `completed` list to decide what's next.

Design note: I deliberately implemented this with a deterministic policy
(rules table) rather than an LLM call. With a 0.5B local model, an LLM-based
supervisor is flaky and slow. The interface is identical — if you want an
LLM-driven variant, replace the body of `supervisor_node` with a prompt call
that returns one of the keys in AGENT_ORDER (or "FINISH"). The graph itself
doesn't change.
"""
from app.graph.state import BriefState

# The canonical pipeline order. The supervisor walks this list and
# dispatches to whichever agent hasn't run yet.
AGENT_ORDER = ["wikipedia", "news", "fact_check", "summarize"]


async def supervisor_node(state: BriefState) -> dict:
    completed = state.get("completed", [])

    for agent in AGENT_ORDER:
        if agent not in completed:
            return {
                "next_action": agent,
                "trace": state.get("trace", []) + [
                    {"node": "supervisor", "next": agent, "completed": list(completed)}
                ],
            }

    # All agents done → hand off to human review
    return {
        "next_action": "review",
        "trace": state.get("trace", []) + [
            {"node": "supervisor", "next": "review", "completed": list(completed)}
        ],
    }