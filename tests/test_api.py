from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from igitdeck.config import Settings
from igitdeck.main import create_app
from igitdeck.models.repo import Platform, RepoIdentity, RepoSource
from igitdeck.models.sync import SyncPhase, SyncRunStatus, SyncTrigger


def test_batch_add_reports_each_line(settings: Settings) -> None:
    app = create_app(settings)

    with TestClient(app) as client:
        first = client.post(
            "/api/repos/batch",
            json={
                "urls": [
                    "https://github.com/psf/requests",
                    "https://github.com/Pallets/Click",
                    "https://example.com/not-a-repo",
                    "   ",
                ]
            },
        )
        assert first.status_code == 200
        body = first.json()
        assert (body["created"], body["existing"], body["failed"]) == (2, 0, 1)
        assert len(body["items"]) == 3
        failed = next(item for item in body["items"] if item["error"])
        assert failed["url"] == "https://example.com/not-a-repo"
        assert "不支持的平台" in failed["error"]
        assert failed["repo"] is None

        again = client.post(
            "/api/repos/batch",
            json={
                "urls": [
                    "pallets/click",
                    "https://gitlab.com/group/project",
                ]
            },
        )
        assert again.status_code == 200
        summary = again.json()
        assert (summary["created"], summary["existing"], summary["failed"]) == (1, 1, 0)
        assert {item["repo"]["full_name"].lower() for item in summary["items"]} == {
            "pallets/click",
            "group/project",
        }

        blank = client.post("/api/repos/batch", json={"urls": ["  ", ""]})
        assert blank.status_code == 400
        assert "没有可添加" in blank.json()["detail"]

        empty = client.post("/api/repos/batch", json={"urls": []})
        assert empty.status_code == 422


def test_api_lifecycle(settings: Settings) -> None:
    app = create_app(settings)

    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        created = client.post(
            "/api/repos",
            json={
                "url": "https://github.com/pallets/click",
                "source": "trending",
                "description": "Command line toolkit",
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["created"] is True
        assert body["repo"]["status"] == "pending"
        assert body["repo"]["source"] == "trending"
        assert body["repo"]["full_name"] == "pallets/click"
        assert body["repo"]["clone_path"] == "/git/github/pallets/click"
        repo_id = body["repo"]["id"]

        duplicate = client.post(
            "/api/repos",
            json={"url": "git@github.com:Pallets/Click.git"},
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["created"] is False
        assert duplicate.json()["repo"]["id"] == repo_id

        second = client.post(
            "/api/repos",
            json={"url": "https://gitlab.com/group/project"},
        )
        assert second.status_code == 201

        listing = client.get("/api/repos", params={"page_size": 1})
        assert listing.status_code == 200
        payload = listing.json()
        assert payload["total"] == 2
        assert payload["pages"] == 2
        assert len(payload["items"]) == 1

        search = client.get("/api/repos", params={"q": "toolkit"})
        assert search.status_code == 200
        assert search.json()["total"] == 1
        assert search.json()["items"][0]["full_name"] == "pallets/click"

        filtered = client.get("/api/repos", params={"platform": "gitlab"})
        assert filtered.json()["total"] == 1

        detail = client.get(f"/api/repos/{repo_id}")
        assert detail.status_code == 200
        detail_body = detail.json()
        assert detail_body["repo"]["description"] == "Command line toolkit"
        assert detail_body["readme"] is None
        assert detail_body["trend"] == []
        assert "sync_runs" not in detail_body

        filters = client.get("/api/filters").json()
        assert {facet["value"]: facet["count"] for facet in filters["platforms"]} == {
            "github": 1,
            "gitlab": 1,
        }
        assert {facet["value"]: facet["count"] for facet in filters["statuses"]}["pending"] == 2

        overview = client.get("/api/overview").json()
        assert overview["repo_count"] == 2
        assert overview["total_code_lines"] == 0
        assert overview["languages"] == []
        assert overview["activity"] == []

        status = client.get("/api/status")
        assert status.status_code == 200
        payload = status.json()
        assert payload["repo_count"] == 2
        assert payload["pending"] == 2
        assert payload["active"] == payload["failed"] == payload["ready"] == 0
        assert payload["auto_sync"] is False
        assert payload["sync_interval_minutes"] == 60
        assert payload["next_sync_at"] is None
        assert payload["due_now"] == 2
        assert payload["total_code_lines"] == 0
        assert isinstance(payload["upcoming"], list)
        assert len(payload["upcoming"]) <= 3
        assert all("next_sync_at" in item for item in payload["upcoming"])
        upcoming_times = [item["next_sync_at"] for item in payload["upcoming"]]
        assert upcoming_times == sorted(upcoming_times)

        runs = client.get("/api/syncs")
        assert runs.status_code == 200
        assert runs.json()["total"] == 0

        container = app.state.container
        run_id = container.sync_runs.start(
            repo_id, trigger=SyncTrigger.MANUAL, started_at=datetime.now(UTC)
        )
        container.sync_runs.finish(
            run_id,
            status=SyncRunStatus.SUCCESS,
            finished_at=datetime.now(UTC),
            message="ok",
            commit_sha="a" * 40,
        )
        feed = client.get("/api/syncs").json()
        assert feed["total"] == 1
        assert feed["items"][0]["full_name"] == "pallets/click"
        assert feed["items"][0]["duration_seconds"] == 0
        failed = client.get("/api/syncs", params={"status": "failed"}).json()
        assert failed["total"] == 0

        missing_readme = client.get(f"/api/repos/{repo_id}/raw/README.md")
        assert missing_readme.status_code == 404

        bad_url = client.post("/api/repos", json={"url": "https://example.com/a/b"})
        assert bad_url.status_code == 400
        assert "不支持的平台" in bad_url.json()["detail"]

        bad_sort = client.get("/api/repos", params={"sort": "invalid"})
        assert bad_sort.status_code == 422
        huge_page = client.get("/api/repos", params={"page": 10**19})
        assert huge_page.status_code == 422

        missing = client.get("/api/repos/99999")
        assert missing.status_code == 404
        huge_id = client.get("/api/repos/99999999999999999999")
        assert huge_id.status_code == 422

        root = client.get("/")
        assert root.status_code == 503
        assert "前端尚未构建" in root.text

        # Removal is an operator action on the host, not a web endpoint.
        assert client.delete(f"/api/repos/{repo_id}").status_code == 405
        assert client.get(f"/api/repos/{repo_id}").status_code == 200
        assert client.get("/api/repos").json()["total"] == 2


def test_bulk_retry_queues_failed_repositories(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(settings)

    with TestClient(app) as client:
        repo_ids = []
        for name in ("bulk-one", "bulk-two"):
            response = client.post("/api/repos", json={"url": f"https://github.com/local/{name}"})
            repo_ids.append(response.json()["repo"]["id"])
        for repo_id in repo_ids:
            app.state.container.repos.mark_failure(repo_id, "boom")

        queued: list[tuple[int, SyncTrigger]] = []

        def fake_request(repo_id: int, trigger: SyncTrigger):
            queued.append((repo_id, trigger))
            return object()

        monkeypatch.setattr(app.state.container.coordinator, "request", fake_request)

        response = client.post("/api/syncs/retry-failed")
        assert response.status_code == 200
        body = response.json()
        assert body["queued"] == 2
        assert set(body["repo_ids"]) == set(repo_ids)
        assert {trigger for _, trigger in queued} == {SyncTrigger.MANUAL}

        app.state.container.progress.update(
            repo_ids[0], phase=SyncPhase.CLONING, percent=42, detail="接收对象"
        )
        snapshot = client.get("/api/syncs/progress").json()
        assert len(snapshot["items"]) == 1
        item = snapshot["items"][0]
        assert item["repo_id"] == repo_ids[0]
        assert item["percent"] == 42
        assert item["phase"] == "cloning"


def test_bulk_retry_without_failures(settings: Settings) -> None:
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post("/api/syncs/retry-failed")
        assert response.status_code == 200
        assert response.json() == {"queued": 0, "repo_ids": []}


def test_status_reports_next_sync_and_recent_activity(settings: Settings) -> None:
    from igitdeck.services.container import build_container

    container = build_container(settings.model_copy(update={"auto_sync": True}))
    container.paths.ensure()
    container.db.migrate()

    record = container.repos.add(
        RepoIdentity(
            platform=Platform.GITHUB,
            owner="local",
            name="scheduled",
            url="https://github.com/local/scheduled.git",
        ),
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    attempted_at = datetime.now(UTC) - timedelta(minutes=10)
    container.repos.mark_syncing(record.id, attempted_at)
    container.repos.mark_success(
        record.id,
        synced_at=attempted_at,
        default_branch="main",
        commit_sha="a" * 40,
        last_commit_at=attempted_at,
        readme_path=None,
        readme_text=None,
        description=None,
    )

    payload = container.dashboard.status()

    assert payload.auto_sync is True
    assert payload.ready == 1
    assert payload.due_now == 0
    assert payload.next_sync_at is not None
    remaining = (payload.next_sync_at - datetime.now(UTC)).total_seconds() / 60
    assert 45 <= remaining <= 51
    assert payload.recent_activity[0].full_name == "local/scheduled"
    assert payload.recent_activity[0].status.value == "ready"
    assert len(payload.upcoming) == 1
    assert payload.upcoming[0].full_name == "local/scheduled"
    assert payload.upcoming[0].next_sync_at == payload.next_sync_at


def test_detail_hides_next_sync_when_scheduling_is_off(
    settings: Settings,
) -> None:
    app = create_app(settings)

    with TestClient(app) as client:
        created = client.post(
            "/api/repos", json={"url": "https://github.com/local/no-schedule"}
        ).json()
        detail = client.get(f"/api/repos/{created['repo']['id']}").json()

    assert detail["next_sync_at"] is None
