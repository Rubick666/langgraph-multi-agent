"""Specialist agents. Each one fetches or produces a piece of the brief.

Every agent follows the same contract:
- Read what it needs from state.
- Return a dict containing ONLY the keys it changed.
- On failure, append to `errors` and mark itself completed, so the
  supervisor doesn't loop forever on a broken agent.
"""
import asyncio
from urllib.parse import quote

import feedparser
import httpx

from app.core.config import settings
from app.graph.state import BriefState


# ---------------------------------------------------------------- Wikipedia
async def wikipedia_agent(state: BriefState) -> dict:
    topic = state.get("topic", "").strip()
    # Wikipedia REST API: /page/summary/{title}. Title must be URL-encoded.
    url = f"{settings.wikipedia_api}/page/summary/{quote(topic, safe='')}"

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(url)
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