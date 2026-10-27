"""The owner/name pair shared by every repository-facing model."""

from __future__ import annotations

from pydantic import BaseModel, computed_field


class RepoNaming(BaseModel):
    owner: str
    name: str

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"
