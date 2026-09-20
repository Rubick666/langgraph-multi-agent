from langgraph.graph import END, START, StateGraph

from app.graph.agents import news_agent, wikipedia_agent
from app.graph.state import BriefState
from app.graph.supervisor import supervisor_node


# Maps the supervisor's `next_action` string → graph node (or END).
ROUTES = {
    "wikipedia": "wikipedia",
    "news": "news",
    "FINISH": END,
}


def _route(state: BriefState) -> str:
    return state.get("next_action", "FINISH")


def build_graph():
    """Return the *uncompiled* graph. Compilation happens in runtime.py where
    the checkpointer is attached."""
    g = StateGraph(BriefState)

    g.add_node("supervisor", supervisor_node)
    g.add_node("wikipedia", wikipedia_agent)
    g.add_node("news", news_agent)

    g.add_edge(START, "supervisor")

    # The supervisor can route to any specialist, or finish.
    g.add_conditional_edges("supervisor", _route, ROUTES)

    # Every specialist returns to the supervisor.
    g.add_edge("wikipedia", "supervisor")
    g.add_edge("news", "supervisor")

    return g