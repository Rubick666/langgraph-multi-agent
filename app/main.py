import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.llm import llm
from app.graph.runtime import close_graph, init_graph
from app.routers import brief, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Ensure the SQLite directory exists
    db_dir = os.path.dirname(settings.database_path) or "."
    os.makedirs(db_dir, exist_ok=True)

    # 2. Compile the graph with the checkpointer attached
    await init_graph(settings.database_path)
    print(f"Graph compiled; checkpointer at {settings.database_path}")

    # 3. Warm up the LLM (small models take a few seconds on first call)
    try:
        await llm.ainvoke("hello")
        print("LLM warmup complete.")
    except Exception as e:
        print(f"LLM warmup failed (will retry on first request): {e}")

    yield

    await close_graph()
    print("SQLite checkpointer closed.")


app = FastAPI(
    title="Research Brief API",
    version="0.1.0",
    description="LangGraph multi-agent research brief generator",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(brief.router)


@app.get("/")
async def root():
    return {"service": "langgraph-multi-agent"}