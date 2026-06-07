from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import List


@dataclass
class DdevLogLine:
    level: str
    message: str


@dataclass
class DdevActionOutput:
    exit_code: int
    lines: List[DdevLogLine]
    raw_output: str

    @property
    def errors(self) -> List[str]:
        return [l.message for l in self.lines if l.level in ("error", "fatal")]

    @property
    def warnings(self) -> List[str]:
        return [l.message for l in self.lines if l.level == "warning"]

    @classmethod
    def empty(cls) -> DdevActionOutput:
        return cls(exit_code=0, lines=[], raw_output="")


@dataclass
class DdevServiceIssue:
    project_name: str
    service_name: str
    status: str

    @property
    def id(self) -> str:
        return f"{self.project_name}-{self.service_name}"


@dataclass
class DdevLogExcerpt:
    project_name: str
    service_name: str
    text: str

    @property
    def id(self) -> str:
        return f"{self.project_name}-{self.service_name}"


@dataclass
class DdevActionReport:
    title: str
    project_names: List[str]
    messages: List[str]
    service_issues: List[DdevServiceIssue]
    log_excerpts: List[DdevLogExcerpt]
    hints: List[str]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
