from __future__ import annotations

from fastapi.testclient import TestClient

from igitdeck.config import Settings
from igitdeck.main import create_app


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
        assert detail_body["sync_runs"] == []

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

        deleted = client.delete(f"/api/repos/{repo_id}")
        assert deleted.status_code == 204
        assert client.get(f"/api/repos/{repo_id}").status_code == 404
        assert client.get("/api/repos").json()["total"] == 1
