"""Expected domain failures. The HTTP layer maps them to status codes."""

from __future__ import annotations


class DomainError(Exception):
    status_code = 400


class InvalidRepoUrl(DomainError):
    status_code = 400


class RepoAlreadyExists(DomainError):
    status_code = 409


class RepoNotFound(DomainError):
    status_code = 404


class RepoFileNotFound(DomainError):
    status_code = 404


class PathOutsideRepo(DomainError):
    status_code = 404


class GitHttpBadRequest(DomainError):
    status_code = 400


class GitHttpBackendError(DomainError):
    status_code = 500


class RequestTooLarge(DomainError):
    status_code = 413
