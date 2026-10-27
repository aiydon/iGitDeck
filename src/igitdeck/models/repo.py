"""Repository domain and API contract, plus canonical Git URL parsing."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import date, datetime
from enum import StrEnum
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, Field, computed_field, field_validator

from igitdeck.models.errors import InvalidRepoUrl
from igitdeck.models.naming import RepoNaming
from igitdeck.models.sync import SyncProgress, SyncRunView
from igitdeck.urls import clone_path


class Platform(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"
    GITEE = "gitee"
    BITBUCKET = "bitbucket"


PLATFORM_HOSTS: dict[Platform, str] = {
    Platform.GITHUB: "github.com",
    Platform.GITLAB: "gitlab.com",
    Platform.GITEE: "gitee.com",
    Platform.BITBUCKET: "bitbucket.org",
}

HOST_TO_PLATFORM: dict[str, Platform] = {
    **{host: platform for platform, host in PLATFORM_HOSTS.items()},
    **{f"www.{host}": platform for platform, host in PLATFORM_HOSTS.items()},
}


class RepoSource(StrEnum):
    MANUAL = "manual"
    TRENDING = "trending"


class RepoStatus(StrEnum):
    PENDING = "pending"
    SYNCING = "syncing"
    READY = "ready"
    ERROR = "error"


class FacetField(StrEnum):
    """Columns that may be grouped for filter facets."""

    PLATFORM = "platform"
    SOURCE = "source"
    STATUS = "status"


class SortField(StrEnum):
    ADDED_AT = "added_at"
    LAST_SYNCED_AT = "last_synced_at"
    LAST_COMMIT_AT = "last_commit_at"
    CODE_LINES = "code_lines"
    DISK_BYTES = "disk_bytes"
    NAME = "name"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class LanguageStat(BaseModel):
    name: str
    code: int = Field(ge=0)
    comment: int = Field(ge=0)
    blank: int = Field(ge=0)
    files: int = Field(ge=0)
    percent: float

    @classmethod
    def decode_many(cls, payload: str) -> list[LanguageStat]:
        """Read the JSON array stored in `repo_snapshots.languages`."""
        return [cls.model_validate(item) for item in json.loads(payload)]

    @classmethod
    def encode_many(cls, languages: Sequence[LanguageStat]) -> str:
        return json.dumps(
            [language.model_dump(mode="json") for language in languages],
            ensure_ascii=False,
            separators=(",", ":"),
        )


class RepoStats(BaseModel):
    captured_at: datetime
    commit_sha: str | None
    code_lines: int = Field(ge=0)
    comment_lines: int = Field(ge=0)
    blank_lines: int = Field(ge=0)
    file_count: int = Field(ge=0)
    disk_bytes: int = Field(ge=0)
    languages: list[LanguageStat] = Field(default_factory=list)


class SnapshotRecord(RepoStats):
    id: int
    repo_id: int


class RepoIdentity(RepoNaming):
    platform: Platform
    url: str


class RepoRecord(RepoNaming):
    id: int
    platform: Platform
    url: str
    source: RepoSource
    status: RepoStatus
    description: str | None
    default_branch: str | None
    readme_path: str | None
    readme_text: str | None
    last_commit_at: datetime | None
    last_synced_at: datetime | None
    last_attempt_at: datetime | None
    consecutive_failures: int
    error_message: str | None
    added_at: datetime
    commit_sha: str | None = None


class HighlightSpan(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class SearchSnippet(BaseModel):
    text: str
    highlights: list[HighlightSpan] = Field(default_factory=list)


class RepoSummary(RepoNaming):
    id: int
    platform: Platform
    url: str
    source: RepoSource
    status: RepoStatus
    description: str | None
    default_branch: str | None
    error_message: str | None
    added_at: datetime
    last_synced_at: datetime | None
    last_commit_at: datetime | None
    last_attempt_at: datetime | None
    consecutive_failures: int
    stats: RepoStats | None
    snippet: SearchSnippet | None = None
    progress: SyncProgress | None = None

    @computed_field
    @property
    def clone_path(self) -> str:
        return clone_path(self.platform, self.owner, self.name)

    @classmethod
    def from_record(
        cls,
        record: RepoRecord,
        *,
        stats: RepoStats | None = None,
        snippet: SearchSnippet | None = None,
        progress: SyncProgress | None = None,
    ) -> RepoSummary:
        return cls(
            id=record.id,
            platform=record.platform,
            owner=record.owner,
            name=record.name,
            url=record.url,
            source=record.source,
            status=record.status,
            description=record.description,
            default_branch=record.default_branch,
            error_message=record.error_message,
            added_at=record.added_at,
            last_synced_at=record.last_synced_at,
            last_commit_at=record.last_commit_at,
            last_attempt_at=record.last_attempt_at,
            consecutive_failures=record.consecutive_failures,
            stats=stats,
            snippet=snippet,
            progress=progress,
        )


class RepoWithStats(BaseModel):
    repo: RepoRecord
    stats: RepoStats | None
    snippet: SearchSnippet | None = None
    progress: SyncProgress | None = None


class TrendPoint(BaseModel):
    """Tracked text lines at one commit on the default branch."""

    committed_at: datetime
    commit_sha: str
    lines: int = Field(ge=0)


class DayActivity(BaseModel):
    day: date
    commits: int = Field(ge=0)


class MonthChurn(BaseModel):
    month: str
    added: int = Field(ge=0)
    deleted: int = Field(ge=0)


class Contributor(BaseModel):
    name: str
    commits: int = Field(ge=0)


class RepoLineTrend(BaseModel):
    commit_sha: str
    generated_at: datetime
    points: list[TrendPoint]
    activity: list[DayActivity] = Field(default_factory=list)
    churn: list[MonthChurn] = Field(default_factory=list)
    contributors: list[Contributor] = Field(default_factory=list)


class ReadmeView(BaseModel):
    path: str
    html: str


class RepoQuery(BaseModel):
    q: str | None = Field(default=None, max_length=200)
    platform: Platform | None = None
    language: str | None = Field(default=None, max_length=100)
    status: RepoStatus | None = None
    source: RepoSource | None = None
    sort: SortField = SortField.ADDED_AT
    order: SortOrder = SortOrder.DESC
    page: int = Field(default=1, ge=1, le=1_000_000)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("q", "language", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class RepoPage(BaseModel):
    items: list[RepoSummary]
    total: int
    page: int
    page_size: int
    pages: int


class SyncQueuedResult(BaseModel):
    queued: bool
    message: str | None = None


class RepoCreateRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    source: RepoSource = RepoSource.MANUAL
    description: str | None = Field(default=None, max_length=2000)


class RepoAddResult(BaseModel):
    repo: RepoSummary
    created: bool


class RepoDetail(BaseModel):
    repo: RepoSummary
    readme: ReadmeView | None
    trend: list[TrendPoint]
    activity: list[DayActivity] = Field(default_factory=list)
    churn: list[MonthChurn] = Field(default_factory=list)
    contributors: list[Contributor] = Field(default_factory=list)
    sync_runs: list[SyncRunView]


_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_segment(value: str, label: str) -> str:
    if value in {"", ".", ".."} or not _SEGMENT.fullmatch(value):
        raise InvalidRepoUrl(f"非法的 {label}: {value!r}")
    if len(value) > 200:
        raise InvalidRepoUrl(f"{label} 过长")
    return value


def _from_host_path(host: str, path: str) -> RepoIdentity:
    normalized_host = host.strip().lower()
    if normalized_host.startswith("www."):
        normalized_host = normalized_host[4:]
    platform = HOST_TO_PLATFORM.get(normalized_host)
    if platform is None:
        supported = ", ".join(PLATFORM_HOSTS.values())
        raise InvalidRepoUrl(f"不支持的平台 {host!r}；支持: {supported}")

    cleaned = unquote(path).strip().strip("/")
    if cleaned.lower().endswith(".git"):
        cleaned = cleaned[:-4]
    parts = [part for part in cleaned.split("/") if part]
    if len(parts) != 2:
        raise InvalidRepoUrl("仓库地址必须形如 https://host/owner/repo")
    owner = _validate_segment(parts[0], "owner")
    name = _validate_segment(parts[1], "仓库名")

    canonical_host = PLATFORM_HOSTS[platform]
    return RepoIdentity(
        platform=platform,
        owner=owner,
        name=name,
        url=f"https://{canonical_host}/{owner}/{name}.git",
    )


def parse_repo_url(raw: str) -> RepoIdentity:
    """Accept HTTPS/HTTP/SSH/SCP/Git URLs, plus owner/repo shorthand."""
    candidate = raw.strip()
    if not candidate:
        raise InvalidRepoUrl("仓库地址不能为空")
    if any(char.isspace() for char in candidate):
        raise InvalidRepoUrl("仓库地址不能包含空白字符")

    if "://" in candidate:
        parts = urlsplit(candidate)
        if parts.scheme.lower() not in {"http", "https", "ssh", "git"}:
            raise InvalidRepoUrl(f"不支持的协议: {parts.scheme}")
        if not parts.hostname:
            raise InvalidRepoUrl("仓库地址缺少主机名")
        return _from_host_path(parts.hostname, parts.path)

    scp_match = re.match(r"^[^@/]+@(?P<host>[^:/]+):(?P<path>.+)$", candidate)
    if scp_match:
        return _from_host_path(scp_match["host"], scp_match["path"])

    if "/" not in candidate:
        raise InvalidRepoUrl("无法识别的仓库地址")
    head, rest = candidate.split("/", 1)
    if "." in head:
        return _from_host_path(head, f"/{rest}")
    if "/" in rest:
        raise InvalidRepoUrl("仓库地址必须形如 owner/repo 或完整 URL")
    return _from_host_path(PLATFORM_HOSTS[Platform.GITHUB], f"/{candidate}")
