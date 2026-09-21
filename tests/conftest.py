import os
import pytest
from fastapi.testclient import TestClient

# Set env BEFORE importing the app so settings pick them up
os.environ["TESTING"] = "1"
os.environ["DATABASE_PATH"] = "./data/test_multiagent.db"


def pytest_sessionfinish(session, exitstatus):
    """Remove the test DB file after the session."""
    for suffix in ("", "-shm", "-wal"):
        p = f"./data/test_multiagent.db{suffix}"
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    """One TestClient for the whole session. Its `with` block runs the
    FastAPI lifespan, compiling the graph and initialising the runtime."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def clean_jobs():
    """Placeholder for a hook if you later want per-test DB cleanup.
    The session-scoped DB is already isolated by TESTING=1."""
    yield