from __future__ import annotations
import json
import os
from pathlib import Path
from typing import List


class PreferencesRepository:
    def __init__(self) -> None:
        config_dir = Path(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")))
        self._path = config_dir / "ddev-menubar" / "preferences.json"

    def load_favourites(self) -> List[str]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text())
            return data.get("favourites", [])
        except Exception:
            return []

    def save_favourites(self, names: List[str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict = {}
        if self._path.exists():
            try:
                existing = json.loads(self._path.read_text())
            except Exception:
                pass
        existing["favourites"] = names
        self._path.write_text(json.dumps(existing, indent=2))
