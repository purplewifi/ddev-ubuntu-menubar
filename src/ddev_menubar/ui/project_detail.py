from __future__ import annotations
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..models.project import DdevProject, DdevProjectDetail
from ..services.project_store import DdevProjectStore


class ProjectDetailView(Gtk.Box):
    def __init__(self, store: DdevProjectStore) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._store = store

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_margin_start(10)
        header.set_margin_end(10)
        header.set_margin_top(8)
        header.set_margin_bottom(8)

        back_btn = Gtk.Button(label="← Back")
        back_btn.get_style_context().add_class("flat")
        back_btn.connect("clicked", lambda _: store.select_project(None))
        header.pack_start(back_btn, False, False, 0)

        self._title_label = Gtk.Label(xalign=0)
        self._title_label.get_style_context().add_class("project-name")
        header.pack_start(self._title_label, True, True, 0)

        self.pack_start(header, False, False, 0)
        self.pack_start(Gtk.Separator(), False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._content_box.set_margin_start(10)
        self._content_box.set_margin_end(10)
        self._content_box.set_margin_top(8)
        self._content_box.set_margin_bottom(8)

        scroll.add(self._content_box)
        self.pack_start(scroll, True, True, 0)

        self.pack_start(Gtk.Separator(), False, False, 0)

        actions_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        actions_bar.set_margin_start(10)
        actions_bar.set_margin_end(10)
        actions_bar.set_margin_top(6)
        actions_bar.set_margin_bottom(8)
        actions_bar.get_style_context().add_class("footer-bar")

        self._start_stop_btn = Gtk.Button()
        self._start_stop_btn.connect("clicked", self._on_start_stop)
        actions_bar.pack_start(self._start_stop_btn, False, False, 0)

        self._restart_btn = Gtk.Button(label="Restart")
        self._restart_btn.connect("clicked", self._on_restart)
        actions_bar.pack_start(self._restart_btn, False, False, 0)

        self._xdebug_btn = Gtk.ToggleButton(label="Xdebug")
        self._xdebug_btn.connect("toggled", self._on_xdebug_toggle)
        actions_bar.pack_start(self._xdebug_btn, False, False, 0)

        more_btn = Gtk.MenuButton(label="More…")
        self._more_menu = Gtk.Menu()
        more_btn.set_popup(self._more_menu)
        actions_bar.pack_start(more_btn, False, False, 0)

        self.pack_end(actions_bar, False, False, 0)
        self._project: DdevProject | None = None
        self._detail: DdevProjectDetail | None = None
        self._xdebug_handler_blocked = False

    def refresh(self, project: DdevProject | None, detail: DdevProjectDetail | None) -> None:
        self._project = project
        self._detail = detail

        name = project.name if project else (detail.name if detail else "Project")
        self._title_label.set_text(name)

        for child in self._content_box.get_children():
            self._content_box.remove(child)

        d = detail or project
        if d is None:
            return

        is_running = (project.is_running if project else False)
        self._start_stop_btn.set_label("Stop" if is_running else "Start")
        self._restart_btn.set_sensitive(is_running)

        self._xdebug_handler_blocked = True
        xdebug = detail.xdebug_enabled if detail else False
        self._xdebug_btn.set_active(bool(xdebug))
        self._xdebug_handler_blocked = False

        def row(key: str, value: str | None) -> Gtk.Box:
            if not value:
                return None
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            k = Gtk.Label(label=key, xalign=0)
            k.get_style_context().add_class("detail-key")
            k.set_size_request(120, -1)
            v = Gtk.Label(label=value, xalign=0)
            v.set_selectable(True)
            v.set_line_wrap(True)
            v.get_style_context().add_class("detail-value")
            box.pack_start(k, False, False, 0)
            box.pack_start(v, True, True, 0)
            return box

        def add(key, value):
            r = row(key, value)
            if r:
                self._content_box.pack_start(r, False, False, 0)

        if hasattr(d, "status"):
            status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            k = Gtk.Label(label="Status", xalign=0)
            k.get_style_context().add_class("detail-key")
            k.set_size_request(120, -1)
            dot = Gtk.Label()
            dot.get_style_context().add_class("status-dot")
            dot.get_style_context().add_class("running" if is_running else "stopped")
            status_lbl = Gtk.Label(
                label=d.status_desc if hasattr(d, "status_desc") else d.status,
                xalign=0,
            )
            status_lbl.get_style_context().add_class(
                "project-status-running" if is_running else "project-status-stopped"
            )
            status_box.pack_start(k, False, False, 0)
            status_box.pack_start(dot, False, False, 0)
            status_box.pack_start(status_lbl, True, True, 0)
            self._content_box.pack_start(status_box, False, False, 0)

        if detail:
            add("Type", detail.type)
            add("PHP Version", detail.php_version)
            add("Web Server", detail.webserver_type)
            add("Node.js", detail.nodejs_version)
            add("Docroot", detail.docroot)
            if detail.database_type and detail.database_version:
                add("Database", f"{detail.database_type} {detail.database_version}")
            elif detail.database_type:
                add("Database", detail.database_type)
            add("Performance", detail.performance_mode)
            add("App Root", detail.approot)
        elif project:
            add("Type", project.type)
            add("App Root", project.approot)

        if project and project.shortroot:
            add("Short Root", project.shortroot)

        self._content_box.pack_start(Gtk.Separator(), False, False, 4)

        urls = []
        if detail and detail.urls:
            urls = detail.urls[:6]
        elif project:
            for u in [project.primary_url, project.httpsurl, project.httpurl]:
                if u and u not in urls:
                    urls.append(u)

        if urls:
            urls_label = Gtk.Label(label="URLs", xalign=0)
            urls_label.get_style_context().add_class("detail-key")
            self._content_box.pack_start(urls_label, False, False, 0)
            for url in urls:
                btn = Gtk.LinkButton(uri=url, label=url)
                btn.get_style_context().add_class("detail-url")
                btn.set_halign(Gtk.Align.START)
                btn.connect("activate-link", lambda w, u=url: (self._store.open_url(u), True)[1])
                self._content_box.pack_start(btn, False, False, 0)

        mailpit_url = (detail.mailpit_url if detail else None) or (project.mailpit_url if project else None)
        if mailpit_url:
            self._content_box.pack_start(Gtk.Separator(), False, False, 4)
            mp_label = Gtk.Label(label="Mailpit", xalign=0)
            mp_label.get_style_context().add_class("detail-key")
            self._content_box.pack_start(mp_label, False, False, 0)
            mp_btn = Gtk.LinkButton(uri=mailpit_url, label=mailpit_url)
            mp_btn.set_halign(Gtk.Align.START)
            mp_btn.connect("activate-link", lambda w, u=mailpit_url: (self._store.open_url(u), True)[1])
            self._content_box.pack_start(mp_btn, False, False, 0)

        if detail and detail.services:
            self._content_box.pack_start(Gtk.Separator(), False, False, 4)
            svc_header = Gtk.Label(label="Services", xalign=0)
            svc_header.get_style_context().add_class("detail-key")
            self._content_box.pack_start(svc_header, False, False, 0)
            for svc_name, svc_info in detail.services.items():
                status = svc_info.status or "unknown"
                svc_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                dot = Gtk.Label()
                dot.get_style_context().add_class("status-dot")
                dot.get_style_context().add_class("running" if status == "running" else "unhealthy" if "unhealthy" in status else "stopped")
                svc_box.pack_start(dot, False, False, 0)
                svc_lbl = Gtk.Label(label=f"{svc_name}: {status}", xalign=0)
                svc_lbl.get_style_context().add_class("detail-value")
                svc_box.pack_start(svc_lbl, True, True, 0)
                self._content_box.pack_start(svc_box, False, False, 0)

        self._rebuild_more_menu()
        self._content_box.show_all()

    def _rebuild_more_menu(self) -> None:
        for child in self._more_menu.get_children():
            self._more_menu.remove(child)

        project = self._project
        if not project:
            return

        def item(label, callback):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda _: callback())
            return mi

        if project.is_running:
            self._more_menu.append(item("Open Site", lambda: self._store.open_primary_url(project)))
            if project.mailpit_url:
                self._more_menu.append(item("Open Mailpit", lambda: self._store.open_mailpit(project)))
            self._more_menu.append(Gtk.SeparatorMenuItem())

        self._more_menu.append(item("SSH", lambda: self._store.ssh_into_project(project.name, project.approot)))
        self._more_menu.append(item("Logs in Terminal", lambda: self._store.show_logs_in_terminal(project.name, project.approot)))
        self._more_menu.append(item("Open Folder", lambda: self._store.reveal_in_files(project)))
        self._more_menu.append(item("Auth SSH", lambda: self._store.auth_ssh_in_terminal()))
        self._more_menu.append(item(
            "View Logs",
            lambda: self._store._emit() or self._request_logs(),
        ))

        self._more_menu.show_all()

    def _request_logs(self) -> None:
        p = self._project
        if p:
            from ..models.project import DdevProject
            project_type = self._detail.type if self._detail else p.type
            self._store._log_request = (p.name, p.approot, project_type)
            self._store._emit()

    def _on_start_stop(self, *_) -> None:
        p = self._project
        if p is None:
            return
        if p.is_running:
            self._store.stop_project(p.name)
        else:
            self._store.start_project(p.name)

    def _on_restart(self, *_) -> None:
        p = self._project
        if p:
            self._store.restart_project(p.name)

    def _on_xdebug_toggle(self, btn: Gtk.ToggleButton) -> None:
        if self._xdebug_handler_blocked:
            return
        p = self._project
        if p:
            self._store.set_xdebug(p.name, btn.get_active())
