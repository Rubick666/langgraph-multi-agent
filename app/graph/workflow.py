from langgraph.graph import END, START, StateGraph

from app.graph.agents import (
    fact_check_agent,
    news_agent,
    review_agent,
    summarize_agent,
    wikipedia_agent,
)
from app.graph.state import BriefState
from app.graph.supervisor import supervisor_node


ROUTES = {
    "wikipedia": "wikipedia",
    "news": "news",
    "fact_check": "fact_check",
    "summarize": "summarize",
    "review": "review",
}


def _route(state: BriefState) -> str:
    return state.get("next_action", "review")


def build_graph():
    g = StateGraph(BriefState)

    g.add_node("supervisor", supervisor_node)
    g.add_node("wikipedia", wikipedia_agent)
    g.add_node("news", news_agent)
    g.add_node("fact_check", fact_check_agent)
    g.add_node("summarize", summarize_agent)
    g.add_node("review", review_agent)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route, ROUTES)

    # Every specialist returns to the supervisor.
    g.add_edge("wikipedia", "supervisor")
    g.add_edge("news", "supervisor")
    g.add_edge("fact_check", "supervisor")
    g.add_edge("summarize", "supervisor")

    # Human review is terminal.
    g.add_edge("review", END)

    return g