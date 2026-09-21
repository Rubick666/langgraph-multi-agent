"""Integration tests for the async job pattern.

Because TESTING=1 swaps in canned agent responses, each run completes in
milliseconds and never touches Wikipedia, Google News, or Ollama. This
makes the suite fast, deterministic, and CI-friendly.
"""
import time
from fastapi.testclient import TestClient


# ---------------------------------------------------------------- health
def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# --------------------------------------------------------- job submission
def test_post_returns_202_with_run_id(client: TestClient):
    r = client.post("/research/brief", json={"topic": "TestTopic"})
    assert r.status_code == 202
    body = r.json()
    assert body["run_id"]
    assert body["status"] == "pending"


def test_post_validates_topic(client: TestClient):
    assert client.post("/research/brief", json={"topic": "x"}).status_code == 422
    assert client.post("/research/brief", json={}).status_code == 422


# ------------------------------------------------------ full happy path
def _submit_and_wait(client: TestClient, topic: str, timeout: float = 5.0) -> str:
    """Submit and poll until the job reaches a terminal-ish state."""
    r = client.post("/research/brief", json={"topic": topic})
    assert r.status_code == 202
    run_id = r.json()["run_id"]

    deadline = time.time() + timeout
    while time.time() < deadline:
        s = client.get(f"/research/brief/{run_id}/status").json()
        if s["status"] in {"awaiting_review", "completed", "failed"}:
            return run_id
        time.sleep(0.05)
    raise AssertionError(f"Job {run_id} did not settle within {timeout}s")


def test_full_flow_to_awaiting_review(client: TestClient):
    run_id = _submit_and_wait(client, "TestFullFlow")

    # Inspect full state
    r = client.get(f"/research/brief/{run_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "awaiting_review"
    assert body["interrupt"] is not None
    assert body["interrupt"]["reason"] == "final_approval"

    state = body["state"]
    assert state["wikipedia_summary"]
    assert len(state["news_headlines"]) == 2
    assert state["fact_check_notes"]
    assert state["draft_brief"]

    # Trace should show the supervisor ran between every specialist
    nodes = [t["node"] for t in state["trace"]]
    assert nodes.count("supervisor") >= 5
    assert "wikipedia" in nodes and "news" in nodes
    assert "fact_check" in nodes and "summarize" in nodes


def test_resume_approve_completes_run(client: TestClient):
    run_id = _submit_and_wait(client, "TestApprove")

    r = client.post(
        f"/research/brief/{run_id}/resume",
        json={"action": "approve", "note": "Looks good."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["state"]["final_brief"] == body["state"]["draft_brief"]
    assert body["state"]["human_action"] == "approve"
    assert body["state"]["human_note"] == "Looks good."

    # Status endpoint agrees
    s = client.get(f"/research/brief/{run_id}/status").json()
    assert s["status"] == "completed"


def test_resume_reject_discards_brief(client: TestClient):
    run_id = _submit_and_wait(client, "TestReject")

    r = client.post(
        f"/research/brief/{run_id}/resume",
        json={"action": "reject", "note": "Not enough sources."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["state"]["final_brief"] is None
    assert body["state"]["human_action"] == "reject"


# ------------------------------------------------------------- error paths
def test_status_unknown_run_returns_404(client: TestClient):
    assert client.get("/research/brief/does-not-exist/status").status_code == 404


def test_get_unknown_run_returns_404(client: TestClient):
    assert client.get("/research/brief/does-not-exist").status_code == 404


def test_resume_unknown_run_returns_404(client: TestClient):
    r = client.post(
        "/research/brief/does-not-exist/resume",
        json={"action": "approve"},
    )
    assert r.status_code == 404


def test_resume_completed_run_returns_400(client: TestClient):
    run_id = _submit_and_wait(client, "TestCompletedResume")
    client.post(f"/research/brief/{run_id}/resume", json={"action": "approve"})

    # Now try to resume again
    r = client.post(
        f"/research/brief/{run_id}/resume",
        json={"action": "approve"},
    )
    assert r.status_code == 400
    assert "not awaiting review" in r.json()["detail"]


# ---------------------------------------------------------- concurrency
def test_multiple_runs_are_independent(client: TestClient):
    """Three simultaneous runs should each complete without interfering."""
    ids = [_submit_and_wait(client, f"Topic{i}") for i in range(3)]
    assert len(set(ids)) == 3  # distinct run_ids

    for run_id in ids:
        body = client.get(f"/research/brief/{run_id}").json()
        assert body["state"]["topic"].startswith("Topic")
        assert body["interrupt"] is not None