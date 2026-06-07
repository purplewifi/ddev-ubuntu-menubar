from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import List


@dataclass
class DdevProjectGroup:
    name: str
    project_names: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "project_names": self.project_names}

    @classmethod
    def from_dict(cls, d: dict) -> DdevProjectGroup:
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            name=d["name"],
            project_names=d.get("project_names", []),
        )


@dataclass
class DdevGroupStatus:
    running: int
    stopped: int
    missing: int

    @property
    def total(self) -> int:
        return self.running + self.stopped + self.missing

    @property
    def summary(self) -> str:
        if self.total == 0:
            return "No projects"
        if self.missing > 0:
            return f"{self.running}/{self.total} running · {self.missing} missing"
        return f"{self.running}/{self.total} running"

    @property
    def all_running(self) -> bool:
        return self.total > 0 and self.running == self.total - self.missing and self.stopped == 0

    @property
    def all_stopped(self) -> bool:
        return self.running == 0
