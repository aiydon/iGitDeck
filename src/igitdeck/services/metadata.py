"""Best-effort description lookup; failures never block a sync or add."""

from __future__ import annotations

import json
import logging
from urllib.parse import quote
from urllib.request import Request, urlopen

from igitdeck.models.repo import Platform, RepoIdentity

logger = logging.getLogger(__name__)


class MetadataClient:
    def __init__(self, *, enabled: bool, timeout_seconds: int) -> None:
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds

    def fetch_description(self, identity: RepoIdentity) -> str | None:
        if not self.enabled or identity.platform is not Platform.GITHUB:
            return None
        url = f"https://api.github.com/repos/{quote(identity.owner)}/{quote(identity.name)}"
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "iGitDeck/0.1",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read(1_000_000))
        except Exception as exc:  # metadata is strictly optional
            logger.debug("metadata lookup failed for %s: %s", identity.full_name, exc)
            return None
        description = payload.get("description")
        if not isinstance(description, str):
            return None
        return description.strip() or None
