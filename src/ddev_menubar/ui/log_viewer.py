from __future__ import annotations
import threading
from typing import Optional

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

from ..models.log_source import LogSource, LogSourceCatalog, LogSourceKind, LogTab
from ..services.ddev_cli import DdevCLI


class LogViewerWindow(Gtk.Window):
    def __init__(self, cli: DdevCLI) -> None:
        super().__init__(title="DDEV Logs")
        self.set_default_size(800, 600)
        self._cli = cli
        self._current_process = None
        self._current_tab_id: Optional[str] = None
        self._project_name: Optional[str] = None
        self._project_type: Optional[str] = None
        self._custom_path: str = ""

        self.connect("delete-event", self._on_close)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(vbox)

        self._header = Gtk.HeaderBar()
        self._header.set_show_close_button(True)
        self._header.set_title("DDEV Logs")
        self.set_titlebar(self._header)

        self._notebook = Gtk.Notebook()
        self._notebook.connect("switch-page", self._on_tab_switch)
        vbox.pack_start(self._notebook, True, True, 0)

        self._text_views: dict = {}
        self._scroll_windows: dict = {}

        self._custom_path_entry = Gtk.Entry()
        self._custom_path_entry.set_placeholder_text("Path inside container (e.g. storage/logs/laravel.log)")
        self._custom_path_entry.connect("activate", self._on_custom_path_changed)

        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bottom_bar.set_margin_start(10)
        bottom_bar.set_margin_end(10)
        bottom_bar.set_margin_top(6)
        bottom_bar.set_margin_bottom(6)

        self._status_label = Gtk.Label(label="", xalign=0)
        self._status_label.get_style_context().add_class("status-bar")
        bottom_bar.pack_start(self._status_label, True, True, 0)

        clear_btn = Gtk.Button(label="Clear")
        clear_btn.connect("clicked", self._on_clear)
        bottom_bar.pack_end(clear_btn, False, False, 0)

        vbox.pack_end(bottom_bar, False, False, 0)
        vbox.pack_end(Gtk.Separator(), False, False, 0)

    def open_for_project(
        self, project_name: str, approot: str, project_type: Optional[str] = None
    ) -> None:
        self._project_name = project_name
        self._project_type = project_type
        self._header.set_title(f"{project_name} - Logs")

        for child in self._notebook.get_children():
            self._notebook.remove(child)
        self._text_views.clear()
        self._scroll_windows.clear()

        tabs = LogSourceCatalog.tabs(project_type)
        for tab in tabs:
            sw, tv = self._make_log_tab()
            self._text_views[tab.id] = tv
            self._scroll_windows[tab.id] = sw

            if tab.is_custom:
                tab_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                entry_box.set_margin_start(8)
                entry_box.set_margin_end(8)
                entry_box.set_margin_top(6)
                entry_box.set_margin_bottom(4)
                entry_box.pack_start(Gtk.Label(label="Path:", xalign=0), False, False, 0)
                entry_box.pack_start(self._custom_path_entry, True, True, 0)
                load_btn = Gtk.Button(label="Load")
                load_btn.connect("clicked", self._on_custom_path_changed)
                entry_box.pack_end(load_btn, False, False, 0)
                tab_box.pack_start(entry_box, False, False, 0)
                tab_box.pack_start(sw, True, True, 0)
                self._notebook.append_page(tab_box, Gtk.Label(label=tab.label))
            else:
                self._notebook.append_page(sw, Gtk.Label(label=tab.label))

        self._notebook.show_all()
        self._notebook.set_current_page(0)
        first_tab = tabs[0] if tabs else None
        if first_tab:
            self._start_log_stream(first_tab)

        self.show_all()
        self.present()

    def _make_log_tab(self):
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        tv = Gtk.TextView()
        tv.set_editable(False)
        tv.set_cursor_visible(False)
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tv.get_style_context().add_class("log-view")

        font_desc = Pango.FontDescription("Monospace 10")
        tv.override_font(font_desc)

        sw.add(tv)
        return sw, tv

    def _on_tab_switch(self, notebook, page, page_num: int) -> None:
        self._stop_stream()
        tabs = LogSourceCatalog.tabs(self._project_type)
        if page_num < len(tabs):
            tab = tabs[page_num]
            if not tab.is_custom:
                self._start_log_stream(tab)

    def _on_custom_path_changed(self, *_) -> None:
        path = self._custom_path_entry.get_text().strip()
        if not path or not self._project_name:
            return
        custom_tab = LogTab("custom", "Custom", LogSource.file(path), is_custom=True)
        self._start_log_stream(custom_tab)

    def _start_log_stream(self, tab: LogTab) -> None:
        if not self._project_name:
            return

        self._stop_stream()
        self._current_tab_id = tab.id
        tv = self._text_views.get(tab.id)
        if tv is None:
            return

        buf = tv.get_buffer()
        buf.set_text("")
        self._set_status("Connecting…")

        source = tab.source
        name = self._project_name

        try:
            if source.kind == LogSourceKind.CONTAINER:
                process = self._cli.stream_container_logs(name, source.service or "web")
            else:
                if not source.path:
                    return
                process = self._cli.stream_file_log(name, source.path)
        except Exception as e:
            self._set_status(f"Error: {e}")
            return

        self._current_process = process

        # Create an end mark in the buffer so we can scroll to it reliably.
        tv_ref = self._text_views.get(tab.id)
        if tv_ref is not None:
            buf_ref = tv_ref.get_buffer()
            if buf_ref.get_mark("stream-end") is None:
                buf_ref.create_mark("stream-end", buf_ref.get_end_iter(), False)

        def reader():
            try:
                # readline() on a bufsize=0 binary pipe gives true line-by-line output
                # with no internal read-ahead buffering.
                while True:
                    raw = process.stdout.readline()
                    if not raw:
                        break
                    line_text = raw.decode("utf-8", errors="replace").rstrip("\n") + "\n"

                    def append(t=line_text, tab_id=tab.id):
                        if self._current_tab_id != tab_id:
                            return False
                        tv = self._text_views.get(tab_id)
                        if tv:
                            buf = tv.get_buffer()
                            buf.insert(buf.get_end_iter(), t)
                            # Move the end mark and scroll to it - more reliable than
                            # adjusting the scrollbar value directly.
                            end_mark = buf.get_mark("stream-end")
                            if end_mark:
                                buf.move_mark(end_mark, buf.get_end_iter())
                                tv.scroll_mark_onscreen(end_mark)
                        return False

                    GLib.idle_add(append)
            except Exception:
                pass
            finally:
                def done(tab_id=tab.id):
                    if self._current_tab_id == tab_id:
                        self._set_status("Stream ended.")
                    return False
                GLib.idle_add(done)

        GLib.idle_add(lambda: self._set_status("Streaming…") or False)
        threading.Thread(target=reader, daemon=True).start()

    def _stop_stream(self) -> None:
        if self._current_process:
            try:
                self._current_process.terminate()
            except Exception:
                pass
            self._current_process = None

    def _on_clear(self, *_) -> None:
        tab_id = self._current_tab_id
        if tab_id and tab_id in self._text_views:
            self._text_views[tab_id].get_buffer().set_text("")

    def _set_status(self, msg: str) -> None:
        self._status_label.set_text(msg)

    def _on_close(self, *_) -> bool:
        self._stop_stream()
        self.hide()
        return True
