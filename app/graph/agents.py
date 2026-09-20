"""Specialist agents. Each one fetches or produces a piece of the brief.

Every agent follows the same contract:
- Read what it needs from state.
- Return a dict containing ONLY the keys it changed.
- On failure, append to `errors` and mark itself completed, so the
  supervisor doesn't loop forever on a broken agent.
"""
import asyncio
from urllib.parse import quote
from langgraph.types import interrupt

import feedparser
import httpx

from app.core.config import settings
from app.graph.state import BriefState
from app.core.llm import llm


# ---------------------------------------------------------------- Wikipedia
WIKI_HEADERS = {
    "User-Agent": "LangGraphMultiAgent/1.0 (https://github.com/Rubick666/langgraph-multi-agent)",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}


async def wikipedia_agent(state: BriefState) -> dict:
    topic = state.get("topic", "").strip()
    url = f"{settings.wikipedia_api}/page/summary/{quote(topic, safe='')}"

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(url, headers=WIKI_HEADERS)
            r.raise_for_status()
            data = r.json()
        summary = data.get("extract") or ""
        page_url = (
            data.get("content_urls", {})
            .get("desktop", {})
            .get("page", "")
        )
        return {
            "wikipedia_summary": summary,
            "wikipedia_url": page_url,
            "completed": state.get("completed", []) + ["wikipedia"],
            "trace": state.get("trace", []) + [
                {"node": "wikipedia", "status": "ok", "chars": len(summary)}
            ],
        }
    except Exception as e:
        return {
            "errors": state.get("errors", []) + [
                {"agent": "wikipedia", "error": f"{type(e).__name__}: {e}"}
            ],
            "completed": state.get("completed", []) + ["wikipedia"],
            "trace": state.get("trace", []) + [
                {"node": "wikipedia", "status": "error", "error": str(e)}
            ],
        }


# ---------------------------------------------------------------- News (RSS)
async def news_agent(state: BriefState) -> dict:
    topic = state.get("topic", "").strip()

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(settings.news_rss_url, params={"q": topic})
            r.raise_for_status()
            xml = r.text

        # feedparser is synchronous — run it off the event loop
        feed = await asyncio.to_thread(feedparser.parse, xml)

        headlines = [
            {
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
            }
            for entry in feed.entries[:5]
        ]

        return {
            "news_headlines": headlines,
            "completed": state.get("completed", []) + ["news"],
            "trace": state.get("trace", []) + [
                {"node": "news", "status": "ok", "count": len(headlines)}
            ],
        }
    except Exception as e:
        return {
            "errors": state.get("errors", []) + [
                {"agent": "news", "error": f"{type(e).__name__}: {e}"}
            ],
            "completed": state.get("completed", []) + ["news"],
            "trace": state.get("trace", []) + [
                {"node": "news", "status": "error", "error": str(e)}
            ],
        }

# ------------------------------------------------------------- Fact checker
async def fact_check_agent(state: BriefState) -> dict:
    """Ask the LLM to identify key claims and check them against the news.

    Uses a strict pipe-separated format so even a small model can produce
    parseable output without JSON-mode prompting.
    """
    wiki = state.get("wikipedia_summary", "")
    headlines = state.get("news_headlines", [])
    news_text = "\n".join(f"- {h['title']}" for h in headlines) or "(no news available)"

    if not wiki:
        return {
            "fact_check_notes": [],
            "completed": state.get("completed", []) + ["fact_check"],
            "trace": state.get("trace", []) + [
                {"node": "fact_check", "status": "skipped", "reason": "no wikipedia summary"}
            ],
        }

    prompt = (
        "You are a fact-checker. From the Wikipedia summary below, identify 2-3 key claims. "
        "For each, say whether the news headlines SUPPORT, CONTRADICT, or DO NOT MENTION it.\n\n"
        "Output one claim per line in this exact format:\n"
        "CLAIM | VERDICT\n\n"
        f"Wikipedia summary:\n{wiki[:800]}\n\n"
        f"News headlines:\n{news_text}\n\n"
        "Fact-check:"
    )

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content or ""
        notes = []
        for line in raw.splitlines():
            line = line.strip()
            if "|" in line:
                claim, verdict = line.split("|", 1)
                claim, verdict = claim.strip(), verdict.strip()
                if claim and verdict:
                    notes.append({"claim": claim, "verdict": verdict})

        return {
            "fact_check_notes": notes,
            "completed": state.get("completed", []) + ["fact_check"],
            "trace": state.get("trace", []) + [
                {"node": "fact_check", "status": "ok", "claims": len(notes)}
            ],
        }
    except Exception as e:
        return {
            "errors": state.get("errors", []) + [
                {"agent": "fact_check", "error": f"{type(e).__name__}: {e}"}
            ],
            "fact_check_notes": [],
            "completed": state.get("completed", []) + ["fact_check"],
            "trace": state.get("trace", []) + [
                {"node": "fact_check", "status": "error", "error": str(e)}
            ],
        }


# ------------------------------------------------------------- Summarizer
async def summarize_agent(state: BriefState) -> dict:
    """Compose the final draft brief from all collected material."""
    wiki = state.get("wikipedia_summary", "")
    headlines = state.get("news_headlines", [])
    notes = state.get("fact_check_notes", [])

    news_text = "\n".join(f"- {h['title']}" for h in headlines) or "(no news available)"
    notes_text = "\n".join(f"- {n['claim']} ({n['verdict']})" for n in notes) or "(no fact-check notes)"

    prompt = (
        "Write a concise research brief (about 1 page) based on the material below. "
        "Structure it as: a one-sentence introduction, 3-4 key points, and a one-sentence conclusion. "
        "Ground every claim in the provided material. Do not invent facts.\n\n"
        f"Wikipedia summary:\n{wiki[:1000]}\n\n"
        f"Recent news headlines:\n{news_text}\n\n"
        f"Fact-check notes:\n{notes_text}\n\n"
        "Brief:"
    )

    try:
        response = await llm.ainvoke(prompt)
        draft = (response.content or "").strip()
        return {
            "draft_brief": draft,
            "completed": state.get("completed", []) + ["summarize"],
            "trace": state.get("trace", []) + [
                {"node": "summarize", "status": "ok", "chars": len(draft)}
            ],
        }
    except Exception as e:
        return {
            "errors": state.get("errors", []) + [
                {"agent": "summarize", "error": f"{type(e).__name__}: {e}"}
            ],
            "draft_brief": None,
            "completed": state.get("completed", []) + ["summarize"],
            "trace": state.get("trace", []) + [
                {"node": "summarize", "status": "error", "error": str(e)}
            ],
        }


# ------------------------------------------------------------ Human review
async def review_agent(state: BriefState) -> dict:
    """Pause the graph and ask a human to approve or reject the draft.

    The payload passed to `interrupt()` is returned to the caller as the
    `interrupt` field in the API response. On resume, `human` is whatever
    the client sent via `Command(resume=...)`.
    """
    payload = {
        "reason": "final_approval",
        "topic": state.get("topic"),
        "draft_brief": state.get("draft_brief"),
        "fact_check_notes": state.get("fact_check_notes", []),
        "error_count": len(state.get("errors", [])),
        "instructions": (
            "Reply with {'action': 'approve'} to publish the brief, "
            "or {'action': 'reject', 'note': '<optional reason>'} to discard it."
        ),
    }

    human = interrupt(payload)
    action = human.get("action", "reject")

    if action == "approve":
        return {
            "final_brief": state.get("draft_brief"),
            "human_action": "approve",
            "human_note": human.get("note"),
            "trace": state.get("trace", []) + [
                {"node": "review", "action": "approve"}
            ],
        }

    return {
        "final_brief": None,
        "human_action": "reject",
        "human_note": human.get("note"),
        "trace": state.get("trace", []) + [
            {"node": "review", "action": "reject"}
        ],
    }