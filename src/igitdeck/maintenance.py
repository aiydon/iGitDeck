"""Operator-only maintenance commands, deliberately not exposed over HTTP.

The dashboard is shared on an intranet without authentication, so removing a
mirror must stay an operator action on the host, not a web endpoint.
"""

from __future__ import annotations

import argparse
import sys

from igitdeck.config import load_settings
from igitdeck.logging_setup import configure_logging
from igitdeck.models.repo import RepoStatus
from igitdeck.services.container import build_container


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="iGitDeck operator maintenance")
    subcommands = parser.add_subparsers(dest="command", required=True)

    remove = subcommands.add_parser("remove", help="delete a repository and its mirror")
    remove.add_argument("repo_id", type=int)
    remove.add_argument(
        "--force",
        action="store_true",
        help="also remove a repository that is currently syncing",
    )

    args = parser.parse_args(argv)
    settings = load_settings()
    configure_logging(
        settings.log_level,
        log_path=settings.logs_dir / "maintenance.log",
        max_bytes=settings.log_max_bytes,
        backup_count=settings.log_backups,
    )

    container = build_container(settings)
    container.paths.ensure()
    container.db.migrate()

    repo = container.repos.get(args.repo_id)
    if repo is None:
        print(f"仓库 {args.repo_id} 不存在", file=sys.stderr)
        return 1
    if repo.status is RepoStatus.SYNCING and not args.force:
        print(
            f"{repo.full_name} 正在同步；确认后使用 --force",
            file=sys.stderr,
        )
        return 1

    container.catalog.delete(repo.id)
    print(f"已删除 {repo.full_name}（数据库记录、镜像与工作区）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
