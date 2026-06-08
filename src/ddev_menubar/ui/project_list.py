from __future__ import annotations
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..models.project import DdevProject
from ..services.project_store import DdevProjectStore


class ProjectListView(Gtk.Box):
    def __init__(self, store: DdevProjectStore) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._store = store

        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        search_box.set_margin_start(10)
        search_box.set_margin_end(10)
        search_box.set_margin_top(6)
        search_box.set_margin_bottom(6)

        search_icon = Gtk.Image.new_from_icon_name("system-search-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
        search_box.pack_start(search_icon, False, False, 0)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("Filter projects…")
        self._search_entry.connect("search-changed", self._on_search_changed)
        search_box.pack_start(self._search_entry, True, True, 0)

        self.pack_start(search_box, False, False, 0)
        self.pack_start(Gtk.Separator(), False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.connect("row-activated", self._on_row_activated)
        scroll.add(self._list_box)
        self.pack_start(scroll, True, True, 0)

        self._empty_label = Gtk.Label(label="No DDEV projects found.")
        self._empty_label.get_style_context().add_class("project-path")
        self._empty_label.set_margin_top(40)

        self._rows: dict = {}

    def refresh(self) -> None:
        projects = self._store.filtered_projects
        selected = self._store.selected_project_name

        for child in self._list_box.get_children():
            self._list_box.remove(child)
        self._rows.clear()

        if not projects:
            msg = "No projects match your filter." if self._store.search_text else "No DDEV projects found."
            empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            lbl = Gtk.Label(label=msg)
            lbl.get_style_context().add_class("project-path")
            lbl.set_margin_top(40)
            empty.pack_start(lbl, False, False, 0)
            row = Gtk.ListBoxRow()
            row.set_selectable(False)
            row.add(empty)
            self._list_box.add(row)
        else:
            for project in projects:
                row = self._make_row(project)
                self._list_box.add(row)
                self._rows[project.name] = row
                if project.name == selected:
                    self._list_box.select_row(row)

        self._list_box.show_all()

    def _make_row(self, project: DdevProject) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.get_style_context().add_class("project-row")
        row._project_name = project.name

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        outer.set_margin_start(4)
        outer.set_margin_end(4)
        outer.set_margin_top(4)
        outer.set_margin_bottom(4)

        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        status_box.set_valign(Gtk.Align.CENTER)
        dot = Gtk.DrawingArea()
        dot.set_size_request(8, 8)
        if project.is_running:
            dot._color = (0.18, 0.80, 0.44, 1.0)
        elif "unhealthy" in project.status_desc.lower():
            dot._color = (0.90, 0.49, 0.13, 1.0)
        else:
            dot._color = (0.56, 0.58, 0.60, 1.0)

        def draw_dot(widget, cr):
            r, g, b, a = widget._color
            cr.set_source_rgba(r, g, b, a)
            w = widget.get_allocated_width()
            h = widget.get_allocated_height()
            cr.arc(w / 2, h / 2, min(w, h) / 2, 0, 6.28318)
            cr.fill()

        dot.connect("draw", draw_dot)
        status_box.pack_start(dot, False, False, 0)
        outer.pack_start(status_box, False, False, 0)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        name_lbl = Gtk.Label(label=project.name, xalign=0)
        name_lbl.get_style_context().add_class("project-name")
        top_row.pack_start(name_lbl, True, True, 0)

        star_lbl = Gtk.Label(label="★")
        star_lbl.get_style_context().add_class("favourite-star")
        star_lbl.set_visible(self._store.is_favourite(project.name))
        top_row.pack_end(star_lbl, False, False, 0)

        status_lbl = Gtk.Label(label=project.status_desc, xalign=1)
        status_lbl.get_style_context().add_class(
            "project-status-running" if project.is_running else "project-status-stopped"
        )
        top_row.pack_end(status_lbl, False, False, 0)
        info_box.pack_start(top_row, False, False, 0)

        path_lbl = Gtk.Label(label=project.shortroot, xalign=0)
        path_lbl.set_ellipsize(3)
        path_lbl.get_style_context().add_class("project-path")
        info_box.pack_start(path_lbl, False, False, 0)

        if project.primary_url:
            url_lbl = Gtk.Label(label=project.primary_url, xalign=0)
            url_lbl.set_ellipsize(3)
            url_lbl.get_style_context().add_class("project-url")
            info_box.pack_start(url_lbl, False, False, 0)

        outer.pack_start(info_box, True, True, 0)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        menu_btn.get_style_context().add_class("flat")
        menu_btn.set_valign(Gtk.Align.CENTER)
        menu = self._make_project_menu(project)
        menu_btn.set_popup(menu)
        outer.pack_end(menu_btn, False, False, 0)

        row.add(outer)
        return row

    def _make_project_menu(self, project: DdevProject) -> Gtk.Menu:
        store = self._store
        menu = Gtk.Menu()

        def item(label: str, callback):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda _: callback())
            return mi

        if project.is_running:
            menu.append(item("Open Site", lambda: store.open_primary_url(project)))
            if project.mailpit_url:
                menu.append(item("Open Mailpit", lambda: store.open_mailpit(project)))
            menu.append(Gtk.SeparatorMenuItem())
            menu.append(item("Stop", lambda: store.stop_project(project.name)))
            menu.append(item("Restart", lambda: store.restart_project(project.name)))
        else:
            menu.append(item("Start", lambda: store.start_project(project.name)))

        menu.append(Gtk.SeparatorMenuItem())
        menu.append(item("Details", lambda: store.select_project(project.name)))
        menu.append(item("Open Folder", lambda: store.reveal_in_files(project)))
        menu.append(item("SSH", lambda: store.ssh_into_project(project.name, project.approot)))
        menu.append(item("Auth SSH", lambda: store.auth_ssh_in_terminal()))
        menu.append(item("View Logs", lambda: self._request_logs(project)))
        menu.append(item("Logs in Terminal", lambda: store.show_logs_in_terminal(project.name, project.approot)))

        menu.append(Gtk.SeparatorMenuItem())
        fav_label = "Unfavourite" if store.is_favourite(project.name) else "Favourite"
        menu.append(item(fav_label, lambda: store.toggle_favourite(project.name)))

        menu.show_all()
        return menu

    def _request_logs(self, project: DdevProject) -> None:
        project_type = project.type
        self._store._log_request = (project.name, project.approot, project_type)
        self._store._emit()

    def _on_row_activated(self, list_box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        name = getattr(row, "_project_name", None)
        if name:
            self._store.select_project(name)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self._store.search_text = entry.get_text()
        self._store._emit()
