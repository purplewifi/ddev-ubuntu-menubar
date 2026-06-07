from __future__ import annotations
import json
import os
from pathlib import Path
from typing import List

from ..models.group import DdevProjectGroup


class ProjectGroupRepository:
    def __init__(self) -> None:
        config_dir = Path(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")))
        self._path = config_dir / "ddev-menubar" / "groups.json"

    def load(self) -> List[DdevProjectGroup]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text())
            return [DdevProjectGroup.from_dict(g) for g in data]
        except Exception:
            return []

    def save(self, groups: List[DdevProjectGroup]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps([g.to_dict() for g in groups], indent=2))
