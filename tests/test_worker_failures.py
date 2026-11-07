from types import SimpleNamespace

import pytest

from review_agent import github, storage


@pytest.mark.parametrize("scenario,expected", [("stale", "stale"), ("large", "skipped"), ("closed", "stale")])
def test_worker_does_not_review_or_publish_unsupported_run(monkeypatch, tmp_path, scenario, expected):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'worker.db'}")
    with storage.session_factory()() as db:
        run = storage.ReviewRun(delivery_id="one", repository="owner/repo", installation_id=1,
                                pr_number=1, head_sha="original", approach="plain", status="queued")
        db.add(run)
        db.commit()
        run_id = run.id

    async def token(_):
        return "mock"

    async def request(token, method, path, **kwargs):
        assert method == "GET"
        return SimpleNamespace(text="x" * 30001, json=lambda: {
            "head": {"sha": "new" if scenario == "stale" else "original"},
            "state": "closed" if scenario == "closed" else "open"})

    async def unexpected(*args, **kwargs):
        raise AssertionError("Model must not run")

    monkeypatch.setattr(github, "installation_token", token)
    monkeypatch.setattr(github, "github_request", request)
    monkeypatch.setattr("review_agent.core.review", unexpected)
    github.process_pull_request(run_id)
    with storage.session_factory()() as db:
        assert db.get(storage.ReviewRun, run_id).status == expected
