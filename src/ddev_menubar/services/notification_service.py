from __future__ import annotations
from typing import List, Optional


class NotificationService:
    _instance: Optional[NotificationService] = None

    def __init__(self) -> None:
        self._available = False
        try:
            import gi
            gi.require_version("Notify", "0.7")
            from gi.repository import Notify
            Notify.init("DDEV Menubar")
            self._available = True
            self._Notify = Notify
        except Exception:
            self._Notify = None

    @classmethod
    def shared(cls) -> NotificationService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def notify_projects_ready(
        self, project_names: List[str], restarted: bool, url: Optional[str] = None
    ) -> None:
        if not self._available:
            return

        count = len(project_names)
        if count == 0:
            return
        if count == 1:
            name = project_names[0]
            title = f"{name} restarted" if restarted else f"{name} is ready"
            body = url or ("Your project is back up and running." if restarted else "Your project started successfully.")
        else:
            title = f"{count} projects restarted" if restarted else f"{count} projects started"
            body = ", ".join(project_names)

        self._post(title, body)

    def notify_projects_failed(
        self, project_names: List[str], restarted: bool, message: str
    ) -> None:
        if not self._available:
            return

        count = len(project_names)
        if count == 0:
            title = "Restart failed" if restarted else "Start failed"
        elif count == 1:
            title = f"{project_names[0]} failed to restart" if restarted else f"{project_names[0]} failed to start"
        else:
            title = f"{count} projects failed to restart" if restarted else f"{count} projects failed to start"

        body = message.split("\n")[0][:200]
        self._post(title, body)

    def _post(self, title: str, body: str) -> None:
        if not self._Notify:
            return
        try:
            n = self._Notify.Notification.new("DDEV Menubar", f"<b>{title}</b>\n{body}", "dialog-information")
            n.show()
        except Exception:
            pass
