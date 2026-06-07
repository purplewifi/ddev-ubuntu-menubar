from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional


class LogSourceKind(Enum):
    CONTAINER = auto()
    FILE = auto()


@dataclass
class LogSource:
    kind: LogSourceKind
    service: Optional[str] = None
    path: Optional[str] = None

    @classmethod
    def container(cls, service: str) -> LogSource:
        return cls(kind=LogSourceKind.CONTAINER, service=service)

    @classmethod
    def file(cls, path: str) -> LogSource:
        return cls(kind=LogSourceKind.FILE, path=path)


@dataclass
class LogTab:
    id: str
    label: str
    source: LogSource
    is_custom: bool = False


class LogSourceCatalog:
    @staticmethod
    def tabs(project_type: Optional[str]) -> List[LogTab]:
        tabs = [
            LogTab("web", "Web", LogSource.container("web")),
            LogTab("db", "DB", LogSource.container("db")),
        ]
        tabs.extend(LogSourceCatalog._file_tabs(project_type))
        tabs.append(LogTab("custom", "Custom", LogSource.file(""), is_custom=True))
        return tabs

    @staticmethod
    def _file_tabs(project_type: Optional[str]) -> List[LogTab]:
        if not project_type:
            return []
        t = project_type.lower()
        if t == "laravel":
            return [LogTab("laravel", "Laravel", LogSource.file("storage/logs/laravel.log"))]
        if t in ("drupal", "drupal6", "drupal7", "drupal8", "drupal9", "drupal10", "drupal11"):
            return [LogTab("drupal", "Drupal", LogSource.file("sites/default/files/debug.log"))]
        if t == "wordpress":
            return [LogTab("wordpress", "WordPress", LogSource.file("wp-content/debug.log"))]
        if t == "typo3":
            return [LogTab("typo3", "TYPO3", LogSource.file("var/log/typo3_site.log"))]
        if t in ("magento", "magento2"):
            return [LogTab("magento", "Magento", LogSource.file("var/log/system.log"))]
        if t == "symfony":
            return [LogTab("symfony", "Symfony", LogSource.file("var/log/dev.log"))]
        return []
