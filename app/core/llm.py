from langchain_ollama import ChatOllama

from app.core.config import settings


llm = ChatOllama(
    model=settings.ollama_model,
    base_url=settings.ollama_host,   # correct param name for langchain-ollama
    temperature=0.2,
    num_predict=400,
    num_ctx=2048,
)