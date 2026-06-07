from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Optional

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3 as AppIndicator
from gi.repository import Gdk, GLib, Gtk

from ..services.project_store import DdevProjectStore
from .css import APP_CSS
from .main_window import MainWindow


def _find_icon(name: str) -> str:
    candidates = [
        Path(__file__).parent.parent.parent.parent / "assets" / name,
        Path("/usr/share/ddev-menubar/assets") / name,
        Path("/usr/local/share/ddev-menubar/assets") / name,
        Path(os.path.expanduser("~/.local/share/ddev-menubar/assets")) / name,
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return name.replace(".svg", "")


class TrayApp:
    def __init__(self) -> None:
        self._store = DdevProjectStore()
        self._main_window: Optional[MainWindow] = None
        self._indicator: Optional[AppIndicator.Indicator] = None

        self._apply_css()
        self._register_icon_theme()

    def run(self) -> None:
        self._main_window = MainWindow(self._store)
        self._indicator = self._create_indicator()
        self._store.add_listener(self._on_store_changed)

        self._store.refresh_projects()
        self._store.start_auto_refresh()

        Gtk.main()

    def _apply_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(APP_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    @staticmethod
    def _register_icon_theme() -> None:
        # Add the assets directory to the icon theme so GNOME Shell can find
        # the icon by name (used in alt-tab, dock, window decorations).
        candidates = [
            Path(__file__).parent.parent.parent.parent / "assets",
            Path("/usr/share/ddev-menubar/assets"),
            Path(os.path.expanduser("~/.local/share/ddev-menubar/assets")),
        ]
        theme = Gtk.IconTheme.get_default()
        for p in candidates:
            if p.exists():
                theme.prepend_search_path(str(p))
                break

    def _create_indicator(self) -> AppIndicator.Indicator:
        icon_path = _find_icon("ddev-menubar.svg")

        indicator = AppIndicator.Indicator.new(
            "ddev-menubar",
            icon_path,
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)

        menu = self._build_indicator_menu()
        indicator.set_menu(menu)
        return indicator

    def _build_indicator_menu(self) -> Gtk.Menu:
        menu = Gtk.Menu()

        self._show_hide_item = Gtk.MenuItem(label="Open DDEV Manager")
        self._show_hide_item.connect("activate", self._on_toggle_window)
        menu.append(self._show_hide_item)

        menu.append(Gtk.SeparatorMenuItem())

        self._projects_item = Gtk.MenuItem(label="No projects loaded")
        self._projects_item.set_sensitive(False)
        menu.append(self._projects_item)

        menu.append(Gtk.SeparatorMenuItem())

        refresh_item = Gtk.MenuItem(label="Refresh")
        refresh_item.connect("activate", lambda _: self._store.refresh_projects(show_activity=True))
        menu.append(refresh_item)

        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit)
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _on_toggle_window(self, *_) -> None:
        if self._main_window:
            self._main_window.toggle_visible()

    def _on_store_changed(self) -> None:
        store = self._store
        running = store.running_count
        total = len(store.projects)

        if total == 0:
            self._projects_item.set_label("No projects loaded")
        else:
            self._projects_item.set_label(f"{running} running · {total} total")

        if self._main_window and self._main_window.get_visible():
            label = "Hide DDEV Manager"
        else:
            label = "Open DDEV Manager"
        self._show_hide_item.set_label(label)

    def _on_quit(self, *_) -> None:
        if self._main_window:
            self._main_window.hide()
        Gtk.main_quit()
