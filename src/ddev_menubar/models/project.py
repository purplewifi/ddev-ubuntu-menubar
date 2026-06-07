from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DdevProject:
    name: str
    approot: str
    shortroot: str
    status: str
    status_desc: str
    type: str
    primary_url: Optional[str] = None
    httpurl: Optional[str] = None
    httpsurl: Optional[str] = None
    mailpit_url: Optional[str] = None
    nodejs_version: Optional[str] = None
    docroot: Optional[str] = None
    mutagen_enabled: Optional[bool] = None
    mutagen_status: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    @classmethod
    def from_dict(cls, d: dict) -> DdevProject:
        return cls(
            name=d["name"],
            approot=d.get("approot", ""),
            shortroot=d.get("shortroot", ""),
            status=d.get("status", ""),
            status_desc=d.get("status_desc", ""),
            type=d.get("type", ""),
            primary_url=d.get("primary_url"),
            httpurl=d.get("httpurl"),
            httpsurl=d.get("httpsurl"),
            mailpit_url=d.get("mailpit_url"),
            nodejs_version=d.get("nodejs_version"),
            docroot=d.get("docroot"),
            mutagen_enabled=d.get("mutagen_enabled"),
            mutagen_status=d.get("mutagen_status"),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DdevProject):
            return False
        return (
            self.name == other.name
            and self.status == other.status
            and self.status_desc == other.status_desc
            and self.primary_url == other.primary_url
            and self.mutagen_status == other.mutagen_status
        )

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass
class DdevServiceInfo:
    short_name: Optional[str] = None
    status: Optional[str] = None
    http_url: Optional[str] = None
    https_url: Optional[str] = None
    host_http_url: Optional[str] = None
    host_https_url: Optional[str] = None
    image: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> DdevServiceInfo:
        return cls(
            short_name=d.get("short_name"),
            status=d.get("status"),
            http_url=d.get("http_url"),
            https_url=d.get("https_url"),
            host_http_url=d.get("host_http_url"),
            host_https_url=d.get("host_https_url"),
            image=d.get("image"),
        )


@dataclass
class DdevDatabaseInfo:
    database_type: Optional[str] = None
    database_version: Optional[str] = None
    published_port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    dbname: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> DdevDatabaseInfo:
        return cls(
            database_type=d.get("database_type"),
            database_version=d.get("database_version"),
            published_port=d.get("published_port"),
            username=d.get("username"),
            password=d.get("password"),
            dbname=d.get("dbname"),
        )


@dataclass
class DdevProjectDetail:
    name: str
    approot: str
    shortroot: str
    status: str
    status_desc: str
    type: str
    php_version: Optional[str] = None
    webserver_type: Optional[str] = None
    nodejs_version: Optional[str] = None
    docroot: Optional[str] = None
    database_type: Optional[str] = None
    database_version: Optional[str] = None
    performance_mode: Optional[str] = None
    xdebug_enabled: Optional[bool] = None
    primary_url: Optional[str] = None
    urls: Optional[list] = None
    mailpit_url: Optional[str] = None
    mailpit_https_url: Optional[str] = None
    services: Optional[dict] = None
    dbinfo: Optional[DdevDatabaseInfo] = None

    @property
    def includes_database_service(self) -> bool:
        if not self.services:
            return False
        return any(k.lower() == "db" for k in self.services)

    @classmethod
    def from_dict(cls, d: dict) -> DdevProjectDetail:
        services = None
        if d.get("services"):
            services = {k: DdevServiceInfo.from_dict(v) for k, v in d["services"].items()}

        dbinfo = None
        if d.get("dbinfo"):
            dbinfo = DdevDatabaseInfo.from_dict(d["dbinfo"])

        return cls(
            name=d["name"],
            approot=d.get("approot", ""),
            shortroot=d.get("shortroot", ""),
            status=d.get("status", ""),
            status_desc=d.get("status_desc", ""),
            type=d.get("type", ""),
            php_version=d.get("php_version"),
            webserver_type=d.get("webserver_type"),
            nodejs_version=d.get("nodejs_version"),
            docroot=d.get("docroot"),
            database_type=d.get("database_type"),
            database_version=d.get("database_version"),
            performance_mode=d.get("performance_mode"),
            xdebug_enabled=d.get("xdebug_enabled"),
            primary_url=d.get("primary_url"),
            urls=d.get("urls"),
            mailpit_url=d.get("mailpit_url"),
            mailpit_https_url=d.get("mailpit_https_url"),
            services=services,
            dbinfo=dbinfo,
        )
