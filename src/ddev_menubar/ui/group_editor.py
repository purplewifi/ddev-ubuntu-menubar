from __future__ import annotations
from typing import List

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..models.group import DdevProjectGroup
from ..models.project import DdevProject
from ..services.project_store import DdevProjectStore


class GroupEditorView(Gtk.Box):
    def __init__(self, store: DdevProjectStore) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._store = store
        self._check_buttons: dict = {}

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_margin_start(10)
        header.set_margin_end(10)
        header.set_margin_top(8)
        header.set_margin_bottom(8)

        back_btn = Gtk.Button(label="← Back")
        back_btn.get_style_context().add_class("flat")
        back_btn.connect("clicked", lambda _: store.cancel_group_editing())
        header.pack_start(back_btn, False, False, 0)

        self._title_label = Gtk.Label(xalign=0)
        self._title_label.get_style_context().add_class("project-name")
        header.pack_start(self._title_label, True, True, 0)

        self.pack_start(header, False, False, 0)
        self.pack_start(Gtk.Separator(), False, False, 0)

        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        form.set_margin_start(10)
        form.set_margin_end(10)
        form.set_margin_top(10)
        form.set_margin_bottom(8)

        name_label = Gtk.Label(label="Group Name", xalign=0)
        name_label.get_style_context().add_class("detail-key")
        form.pack_start(name_label, False, False, 0)

        self._name_entry = Gtk.Entry()
        self._name_entry.set_placeholder_text("e.g. Production")
        form.pack_start(self._name_entry, False, False, 0)

        projects_label = Gtk.Label(label="Projects", xalign=0)
        projects_label.get_style_context().add_class("detail-key")
        form.pack_start(projects_label, False, False, 0)

        self.pack_start(form, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.add(self._list_box)
        self.pack_start(scroll, True, True, 0)

        self.pack_start(Gtk.Separator(), False, False, 0)

        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bottom.set_margin_start(10)
        bottom.set_margin_end(10)
        bottom.set_margin_top(6)
        bottom.set_margin_bottom(8)

        self._save_btn = Gtk.Button(label="Save")
        self._save_btn.get_style_context().add_class("suggested-action")
        self._save_btn.connect("clicked", self._on_save)
        bottom.pack_end(self._save_btn, False, False, 0)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: store.cancel_group_editing())
        bottom.pack_end(cancel_btn, False, False, 0)

        self.pack_end(bottom, False, False, 0)

    def refresh(self) -> None:
        group = self._store.editing_group
        projects = self._store.projects

        is_new = group is None or not any(g.id == group.id for g in self._store.groups)
        self._title_label.set_text("New Group" if is_new else f"Edit {group.name}")

        if group:
            self._name_entry.set_text(group.name)

        for child in self._list_box.get_children():
            self._list_box.remove(child)
        self._check_buttons.clear()

        selected_names = set(group.project_names) if group else set()

        for project in projects:
            row = Gtk.ListBoxRow()
            row.set_selectable(False)

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_margin_start(10)
            box.set_margin_end(10)
            box.set_margin_top(6)
            box.set_margin_bottom(6)

            cb = Gtk.CheckButton()
            cb.set_active(project.name in selected_names)
            box.pack_start(cb, False, False, 0)
            self._check_buttons[project.name] = cb

            dot = Gtk.Label()
            dot.get_style_context().add_class("status-dot")
            dot.get_style_context().add_class("running" if project.is_running else "stopped")
            box.pack_start(dot, False, False, 0)

            name_lbl = Gtk.Label(label=project.name, xalign=0)
            name_lbl.get_style_context().add_class("project-name")
            box.pack_start(name_lbl, True, True, 0)

            row.add(box)
            self._list_box.add(row)

        self._list_box.show_all()

    def _on_save(self, *_) -> None:
        group = self._store.editing_group
        if group is None:
            return

        group.name = self._name_entry.get_text()
        group.project_names = [
            name for name, cb in self._check_buttons.items() if cb.get_active()
        ]
        self._store.save_group(group)
