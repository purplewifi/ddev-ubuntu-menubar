from __future__ import annotations
from datetime import datetime
from typing import Optional

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from ..services.project_store import DdevProjectStore
from .action_report_view import ActionReportDialog
from .group_editor import GroupEditorView
from .group_list import GroupDetailView, GroupListView
from .log_viewer import LogViewerWindow
from .project_detail import ProjectDetailView
from .project_list import ProjectListView
from .startup_progress_view import StartupProgressView


class MainWindow(Gtk.Window):
    def __init__(self, store: DdevProjectStore) -> None:
        super().__init__()
        self._store = store
        self._log_viewer: Optional[LogViewerWindow] = None

        self.set_title("DDEV Menubar")
        self.set_decorated(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_resizable(True)
        self.set_default_size(420, 580)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.set_wmclass("ddev-menubar", "ddev-menubar")

        self.connect("delete-event", self._on_delete)
        self.connect("focus-out-event", self._on_focus_out)

        self._build_ui()
        store.add_listener(self._on_store_changed)

    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_margin_start(12)
        header.set_margin_end(12)
        header.set_margin_top(8)
        header.set_margin_bottom(8)

        title_lbl = Gtk.Label(label="DDEV")
        title_lbl.get_style_context().add_class("project-name")
        header.pack_start(title_lbl, False, False, 0)

        self._spinner = Gtk.Spinner()
        self._spinner.set_size_request(16, 16)
        header.pack_start(self._spinner, False, False, 0)

        self._summary_label = Gtk.Label(label="", xalign=1)
        self._summary_label.get_style_context().add_class("project-path")
        header.pack_end(self._summary_label, False, False, 0)

        root.pack_start(header, False, False, 0)

        self._tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._tab_bar.set_margin_start(12)
        self._tab_bar.set_margin_end(12)
        self._tab_bar.set_margin_bottom(8)

        self._projects_tab_btn = Gtk.ToggleButton(label="Projects")
        self._projects_tab_btn.set_active(True)
        self._projects_tab_btn.connect("toggled", lambda _: self._on_tab_toggle("projects"))
        self._tab_bar.pack_start(self._projects_tab_btn, True, True, 0)

        self._groups_tab_btn = Gtk.ToggleButton(label="Groups")
        self._groups_tab_btn.connect("toggled", lambda _: self._on_tab_toggle("groups"))
        self._tab_bar.pack_start(self._groups_tab_btn, True, True, 0)

        root.pack_start(self._tab_bar, False, False, 0)
        root.pack_start(Gtk.Separator(), False, False, 0)

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(100)
        root.pack_start(self._stack, True, True, 0)

        self._unavailable_view = self._make_unavailable_view()
        self._stack.add_named(self._unavailable_view, "unavailable")

        self._loading_view = self._make_loading_view()
        self._stack.add_named(self._loading_view, "loading")

        self._project_list_view = ProjectListView(self._store)
        self._stack.add_named(self._project_list_view, "project_list")

        self._project_detail_view = ProjectDetailView(self._store)
        self._stack.add_named(self._project_detail_view, "project_detail")

        self._loading_detail_view = self._make_loading_detail_view()
        self._stack.add_named(self._loading_detail_view, "loading_detail")

        self._group_list_view = GroupListView(self._store)
        self._stack.add_named(self._group_list_view, "group_list")

        self._group_detail_view = GroupDetailView(self._store)
        self._stack.add_named(self._group_detail_view, "group_detail")

        self._group_editor_view = GroupEditorView(self._store)
        self._stack.add_named(self._group_editor_view, "group_editor")

        root.pack_start(Gtk.Separator(), False, False, 0)

        self._progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._progress_separator = Gtk.Separator()
        self._progress_widget = StartupProgressView()
        self._progress_box.pack_start(self._progress_separator, False, False, 0)
        self._progress_box.pack_start(self._progress_widget, False, False, 0)
        root.pack_start(self._progress_box, False, False, 0)

        root.pack_start(Gtk.Separator(), False, False, 0)

        self._status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._status_bar.set_margin_start(10)
        self._status_bar.set_margin_end(10)
        self._status_bar.set_margin_top(4)
        self._status_bar.set_margin_bottom(4)
        self._status_label = Gtk.Label(label="", xalign=0)
        self._status_label.set_ellipsize(3)
        self._status_label.get_style_context().add_class("status-bar")
        self._status_bar_spinner = Gtk.Spinner()
        self._status_bar_spinner.set_size_request(14, 14)
        self._status_bar.pack_start(self._status_bar_spinner, False, False, 0)
        self._status_bar.pack_start(self._status_label, True, True, 0)
        root.pack_start(self._status_bar, False, False, 0)

        self._mkcert_banner = self._make_mkcert_banner()
        root.pack_start(self._mkcert_banner, False, False, 0)
        self._mkcert_banner_sep = Gtk.Separator()
        root.pack_start(self._mkcert_banner_sep, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        footer.set_margin_start(10)
        footer.set_margin_end(10)
        footer.set_margin_top(6)
        footer.set_margin_bottom(8)
        footer.get_style_context().add_class("footer-bar")

        self._new_group_btn = Gtk.Button(label="New Group")
        self._new_group_btn.connect("clicked", lambda _: self._store.begin_create_group())
        footer.pack_start(self._new_group_btn, False, False, 0)

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.connect("clicked", lambda _: self._store.refresh_projects(show_activity=True))
        footer.pack_start(refresh_btn, False, False, 0)

        auth_ssh_btn = Gtk.Button(label="Auth SSH")
        auth_ssh_btn.connect("clicked", lambda _: self._store.auth_ssh_in_terminal())
        footer.pack_start(auth_ssh_btn, False, False, 0)

        self._last_refreshed_label = Gtk.Label(label="", xalign=1)
        self._last_refreshed_label.get_style_context().add_class("project-path")
        footer.pack_end(self._last_refreshed_label, False, False, 0)

        about_btn = Gtk.Button()
        about_btn.set_image(Gtk.Image.new_from_icon_name("dialog-information-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        about_btn.get_style_context().add_class("flat")
        about_btn.connect("clicked", self._on_about)
        footer.pack_end(about_btn, False, False, 0)

        root.pack_start(footer, False, False, 0)

        root.show_all()
        self._progress_box.hide()
        self._mkcert_banner.hide()
        self._mkcert_banner_sep.hide()
        self._spinner.hide()

    def _make_unavailable_view(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic", Gtk.IconSize.DIALOG)
        box.pack_start(icon, False, False, 0)
        lbl = Gtk.Label(label="DDEV Not Found")
        lbl.get_style_context().add_class("project-name")
        box.pack_start(lbl, False, False, 0)
        sub = Gtk.Label(label="Install DDEV or ensure it is available in your PATH.")
        sub.get_style_context().add_class("project-path")
        sub.set_line_wrap(True)
        sub.set_max_width_chars(40)
        box.pack_start(sub, False, False, 0)
        return box

    def _make_loading_view(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        spinner = Gtk.Spinner()
        spinner.set_size_request(32, 32)
        spinner.start()
        box.pack_start(spinner, False, False, 0)
        lbl = Gtk.Label(label="Loading DDEV projects…")
        lbl.get_style_context().add_class("project-path")
        box.pack_start(lbl, False, False, 0)
        return box

    def _make_loading_detail_view(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        spinner = Gtk.Spinner()
        spinner.set_size_request(24, 24)
        spinner.start()
        box.pack_start(spinner, False, False, 0)
        lbl = Gtk.Label(label="Loading project details…")
        lbl.get_style_context().add_class("project-path")
        box.pack_start(lbl, False, False, 0)
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self._store.select_project(None))
        box.pack_start(cancel_btn, False, False, 0)
        return box

    def _make_mkcert_banner(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.get_style_context().add_class("mkcert-banner")

        icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
        box.pack_start(icon, False, False, 0)

        lbl = Gtk.Label(label="mkcert not trusted - HTTPS will show browser warnings", xalign=0)
        lbl.get_style_context().add_class("mkcert-banner-label")
        lbl.set_ellipsize(3)
        box.pack_start(lbl, True, True, 0)

        fix_btn = Gtk.Button(label="Fix")
        fix_btn.set_tooltip_text("Run mkcert -install in a terminal")
        fix_btn.connect("clicked", lambda _: self._store.fix_mkcert())
        box.pack_end(fix_btn, False, False, 0)

        return box

    def _on_tab_toggle(self, tab: str) -> None:
        active_projects = self._projects_tab_btn.get_active()
        active_groups = self._groups_tab_btn.get_active()

        if tab == "projects" and not active_projects:
            self._projects_tab_btn.handler_block_by_func(lambda _: self._on_tab_toggle("projects"))
            self._projects_tab_btn.set_active(True)
            self._projects_tab_btn.handler_unblock_by_func(lambda _: self._on_tab_toggle("projects"))
            return

        if tab == "groups" and not active_groups:
            self._groups_tab_btn.handler_block_by_func(lambda _: self._on_tab_toggle("groups"))
            self._groups_tab_btn.set_active(True)
            self._groups_tab_btn.handler_unblock_by_func(lambda _: self._on_tab_toggle("groups"))
            return

        if tab == "projects" and active_projects:
            self._groups_tab_btn.set_active(False)
            self._store.select_tab("projects")
        elif tab == "groups" and active_groups:
            self._projects_tab_btn.set_active(False)
            self._store.select_tab("groups")

    def toggle_visible(self) -> None:
        if self.get_visible():
            self.hide()
        else:
            self._position_near_tray()
            self.show_all()
            self._update_ui()
            self.present()
            self._store.start_auto_refresh()
            self._store.refresh_projects()

    def _position_near_tray(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        monitor = display.get_primary_monitor()
        if monitor is None:
            return
        geometry = monitor.get_geometry()
        workarea = monitor.get_workarea()
        win_width, win_height = self.get_size()
        x = workarea.x + workarea.width - win_width - 10
        y = workarea.y + 10
        self.move(x, y)

    def _on_focus_out(self, window: Gtk.Window, event: Gdk.Event) -> bool:
        return False

    def _on_delete(self, *_) -> bool:
        self.hide()
        self._store.stop_auto_refresh()
        return True

    def _on_store_changed(self) -> None:
        self._update_ui()
        self._check_log_request()
        self._check_action_report()

    def _update_ui(self) -> None:
        store = self._store

        running = store.running_count
        total = len(store.projects)
        self._summary_label.set_text(f"{running} running · {total} total")

        if store.is_loading or store.is_performing_action:
            self._spinner.start()
            self._spinner.show()
        else:
            self._spinner.stop()
            self._spinner.hide()

        if store.last_refreshed:
            ts = store.last_refreshed.strftime("%H:%M:%S")
            self._last_refreshed_label.set_text(f"Updated {ts}")

        self._new_group_btn.set_visible(
            store.main_tab == "groups" and not store.is_editing_group and not store.selected_group_id
        )

        if store.startup_progress:
            self._progress_widget.update(store.startup_progress)
            self._progress_box.show_all()
        else:
            self._progress_box.hide()

        show_mkcert = store.mkcert_needs_install
        self._mkcert_banner.set_visible(show_mkcert)
        self._mkcert_banner_sep.set_visible(show_mkcert)

        msg = store.activity_message or store.status_message or ""
        self._status_label.set_text(msg)
        if store.is_performing_action or store.is_refreshing:
            self._status_bar_spinner.start()
            self._status_bar_spinner.show()
        else:
            self._status_bar_spinner.stop()
            self._status_bar_spinner.hide()

        if not store.ddev_available:
            self._stack.set_visible_child_name("unavailable")
        elif store.is_loading and not store.projects:
            self._stack.set_visible_child_name("loading")
        elif store.main_tab == "groups":
            if store.is_editing_group and store.editing_group is not None:
                self._group_editor_view.refresh()
                self._stack.set_visible_child_name("group_editor")
            elif store.selected_group_id:
                self._group_detail_view.refresh()
                self._stack.set_visible_child_name("group_detail")
            else:
                self._group_list_view.refresh()
                self._stack.set_visible_child_name("group_list")
        else:
            if store.selected_project_name and not store.selected_detail:
                self._stack.set_visible_child_name("loading_detail")
            elif store.selected_detail:
                self._project_detail_view.refresh(store.selected_project, store.selected_detail)
                self._stack.set_visible_child_name("project_detail")
            else:
                self._project_list_view.refresh()
                self._stack.set_visible_child_name("project_list")

        self._tab_bar.set_visible(
            not (store.selected_project_name or store.selected_group_id or store.is_editing_group)
        )

    def _check_log_request(self) -> None:
        req = getattr(self._store, "_log_request", None)
        if req is None:
            return
        self._store._log_request = None
        name, approot, project_type = req
        if self._log_viewer is None:
            self._log_viewer = LogViewerWindow(self._store._cli)
        self._log_viewer.open_for_project(name, approot, project_type)

    def _check_action_report(self) -> None:
        report = self._store.action_report
        if report is None:
            return
        ActionReportDialog(self, self._store, report)

    def _on_about(self, *_) -> None:
        dialog = Gtk.AboutDialog()
        dialog.set_transient_for(self)
        dialog.set_modal(True)
        dialog.set_program_name("DDEV Menubar")
        dialog.set_comments("DDEV project manager for Ubuntu")
        dialog.set_website("https://ddev.com")

        path = self._store.ddev_executable_path
        version_text = f"DDEV at: {path}" if path else "DDEV not found"
        dialog.set_version(version_text)

        dialog.run()
        dialog.destroy()
