# Research Brief API (langgraph-multi-agent)

A supervisor-based multi-agent system that turns a topic into a research brief
by delegating to Wikipedia and News specialist agents.

## Quick Start

1. `docker-compose up --build`
2. Pull the model (one-time, ~400 MB):
   `docker-compose exec ollama ollama pull qwen2.5:0.5b`
3. Health: `http://localhost:8000/health`
4. Docs: `http://localhost:8000/docs`

## API

`POST /research/brief` with body `{"topic": "Tesla"}` returns the collected
data plus a trace of which agent contributed what.