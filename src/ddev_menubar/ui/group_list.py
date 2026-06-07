from __future__ import annotations
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..models.group import DdevProjectGroup
from ..services.project_store import DdevProjectStore


class GroupListView(Gtk.Box):
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
        self._search_entry.set_placeholder_text("Filter groups…")
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

    def refresh(self) -> None:
        for child in self._list_box.get_children():
            self._list_box.remove(child)

        groups = self._store.filtered_groups
        selected_id = self._store.selected_group_id

        if not groups:
            empty = Gtk.ListBoxRow()
            empty.set_selectable(False)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            lbl = Gtk.Label(label="No groups yet. Create one below.")
            lbl.get_style_context().add_class("project-path")
            lbl.set_margin_top(40)
            box.pack_start(lbl, False, False, 0)
            empty.add(box)
            self._list_box.add(empty)
        else:
            for group in groups:
                row = self._make_row(group)
                self._list_box.add(row)
                if group.id == selected_id:
                    self._list_box.select_row(row)

        self._list_box.show_all()

    def _make_row(self, group: DdevProjectGroup) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.get_style_context().add_class("group-row")
        row._group_id = group.id

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        outer.set_margin_start(6)
        outer.set_margin_end(6)
        outer.set_margin_top(4)
        outer.set_margin_bottom(4)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        name_lbl = Gtk.Label(label=group.name, xalign=0)
        name_lbl.get_style_context().add_class("group-name")
        info_box.pack_start(name_lbl, False, False, 0)

        status = self._store.group_status(group)
        summary_lbl = Gtk.Label(label=status.summary, xalign=0)
        summary_lbl.get_style_context().add_class("group-summary")
        info_box.pack_start(summary_lbl, False, False, 0)

        outer.pack_start(info_box, True, True, 0)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        menu_btn.get_style_context().add_class("flat")
        menu_btn.set_valign(Gtk.Align.CENTER)
        menu = self._make_group_menu(group)
        menu_btn.set_popup(menu)
        outer.pack_end(menu_btn, False, False, 0)

        row.add(outer)
        return row

    def _make_group_menu(self, group: DdevProjectGroup) -> Gtk.Menu:
        store = self._store
        menu = Gtk.Menu()

        def item(label: str, callback):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda _: callback())
            return mi

        status = store.group_status(group)
        if not status.all_running:
            menu.append(item("Start All", lambda: store.start_group(group)))
        if not status.all_stopped:
            menu.append(item("Stop All", lambda: store.stop_group(group)))
        menu.append(item("Restart All", lambda: store.restart_group(group)))
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(item("Edit", lambda: store.begin_edit_group(group)))
        menu.append(item("Delete", lambda: self._confirm_delete(group)))

        menu.show_all()
        return menu

    def _confirm_delete(self, group: DdevProjectGroup) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f'Delete group "{group.name}"?',
        )
        dialog.format_secondary_text("This cannot be undone.")
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.OK:
            self._store.delete_group(group)

    def _on_row_activated(self, list_box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        group_id = getattr(row, "_group_id", None)
        if group_id:
            self._store.select_group(group_id)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self._store.group_search_text = entry.get_text()
        self._store._emit()


class GroupDetailView(Gtk.Box):
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
        back_btn.connect("clicked", lambda _: store.select_group(None))
        header.pack_start(back_btn, False, False, 0)

        self._title_label = Gtk.Label(xalign=0)
        self._title_label.get_style_context().add_class("project-name")
        header.pack_start(self._title_label, True, True, 0)

        self._edit_btn = Gtk.Button(label="Edit")
        self._edit_btn.get_style_context().add_class("flat")
        header.pack_end(self._edit_btn, False, False, 0)
        self.pack_start(header, False, False, 0)
        self.pack_start(Gtk.Separator(), False, False, 0)

        self._summary_label = Gtk.Label(xalign=0)
        self._summary_label.set_margin_start(10)
        self._summary_label.set_margin_end(10)
        self._summary_label.set_margin_top(6)
        self._summary_label.set_margin_bottom(6)
        self._summary_label.get_style_context().add_class("group-summary")
        self.pack_start(self._summary_label, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.add(self._list_box)
        self.pack_start(scroll, True, True, 0)

        self.pack_start(Gtk.Separator(), False, False, 0)

        actions_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        actions_bar.set_margin_start(10)
        actions_bar.set_margin_end(10)
        actions_bar.set_margin_top(6)
        actions_bar.set_margin_bottom(8)

        self._start_btn = Gtk.Button(label="Start All")
        self._start_btn.connect("clicked", lambda _: self._on_start())
        actions_bar.pack_start(self._start_btn, False, False, 0)

        self._stop_btn = Gtk.Button(label="Stop All")
        self._stop_btn.connect("clicked", lambda _: self._on_stop())
        actions_bar.pack_start(self._stop_btn, False, False, 0)

        self._restart_btn = Gtk.Button(label="Restart All")
        self._restart_btn.connect("clicked", lambda _: self._on_restart())
        actions_bar.pack_start(self._restart_btn, False, False, 0)

        self.pack_end(actions_bar, False, False, 0)
        self._group = None

    def refresh(self) -> None:
        group = self._store.selected_group
        if group is None:
            return
        self._group = group

        self._title_label.set_text(group.name)

        def on_edit(*_):
            self._store.begin_edit_group(group)
        self._edit_btn.connect("clicked", on_edit)

        status = self._store.group_status(group)
        self._summary_label.set_text(status.summary)
        self._start_btn.set_sensitive(not status.all_running)
        self._stop_btn.set_sensitive(not status.all_stopped)

        for child in self._list_box.get_children():
            self._list_box.remove(child)

        known = {p.name: p for p in self._store.projects}
        for name in group.project_names:
            row = Gtk.ListBoxRow()
            row.set_selectable(False)

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_margin_start(10)
            box.set_margin_end(10)
            box.set_margin_top(6)
            box.set_margin_bottom(6)

            project = known.get(name)
            is_running = project.is_running if project else False

            dot = Gtk.DrawingArea()
            dot.set_size_request(8, 8)
            if project is None:
                dot._color = (0.56, 0.58, 0.60, 0.4)
            elif is_running:
                dot._color = (0.18, 0.80, 0.44, 1.0)
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

            box.pack_start(dot, False, False, 0)

            name_lbl = Gtk.Label(label=name, xalign=0)
            name_lbl.get_style_context().add_class("project-name")
            if project is None:
                name_lbl.get_style_context().add_class("project-path")
            box.pack_start(name_lbl, True, True, 0)

            if project is None:
                missing_lbl = Gtk.Label(label="missing", xalign=1)
                missing_lbl.get_style_context().add_class("project-path")
                box.pack_end(missing_lbl, False, False, 0)
            else:
                open_btn = Gtk.Button(label="→")
                open_btn.get_style_context().add_class("flat")
                pname = name
                open_btn.connect("clicked", lambda _, n=pname: self._store.open_project_from_group(n))
                box.pack_end(open_btn, False, False, 0)

            row.add(box)
            self._list_box.add(row)

        self._list_box.show_all()

    def _on_start(self) -> None:
        if self._group:
            self._store.start_group(self._group)

    def _on_stop(self) -> None:
        if self._group:
            self._store.stop_group(self._group)

    def _on_restart(self) -> None:
        if self._group:
            self._store.restart_group(self._group)
