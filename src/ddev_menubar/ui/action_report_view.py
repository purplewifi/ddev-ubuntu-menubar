from __future__ import annotations
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..models.action_report import DdevActionReport
from ..services.project_store import DdevProjectStore


class ActionReportDialog(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window, store: DdevProjectStore, report: DdevActionReport) -> None:
        super().__init__(title=report.title, transient_for=parent, modal=True)
        self.set_default_size(500, 400)
        self.add_button("Close", Gtk.ResponseType.CLOSE)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(12)

        if report.messages:
            section = self._section("Issues")
            content.pack_start(section, False, False, 0)
            for msg in report.messages:
                lbl = Gtk.Label(label=msg, xalign=0)
                lbl.set_line_wrap(True)
                lbl.set_selectable(True)
                content.pack_start(lbl, False, False, 0)

        if report.service_issues:
            section = self._section("Service Status")
            content.pack_start(section, False, False, 0)
            for issue in report.service_issues:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                row.pack_start(Gtk.Label(label=f"{issue.project_name}: {issue.service_name}", xalign=0), False, False, 0)
                status = Gtk.Label(label=issue.status, xalign=0)
                status.get_style_context().add_class("project-status-stopped")
                row.pack_start(status, False, False, 0)
                content.pack_start(row, False, False, 0)

        if report.log_excerpts:
            section = self._section("Log Excerpts")
            content.pack_start(section, False, False, 0)
            for excerpt in report.log_excerpts:
                lbl = Gtk.Label(
                    label=f"{excerpt.project_name} / {excerpt.service_name}:", xalign=0
                )
                lbl.get_style_context().add_class("project-name")
                content.pack_start(lbl, False, False, 0)
                frame = Gtk.Frame()
                tv = Gtk.TextView()
                tv.set_editable(False)
                tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
                tv.get_buffer().set_text(excerpt.text)
                tv.get_style_context().add_class("excerpt-box")
                frame.add(tv)
                content.pack_start(frame, False, False, 0)

        if report.hints:
            section = self._section("Hints")
            content.pack_start(section, False, False, 0)
            for hint in report.hints:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                row.pack_start(Gtk.Label(label="•", xalign=0), False, False, 0)
                lbl = Gtk.Label(label=hint, xalign=0)
                lbl.set_line_wrap(True)
                lbl.get_style_context().add_class("hint-row")
                row.pack_start(lbl, True, True, 0)
                content.pack_start(row, False, False, 0)

        scroll.add(content)
        self.get_content_area().pack_start(scroll, True, True, 0)
        self.show_all()

        self.connect("response", lambda d, r: (store.dismiss_action_report(), d.destroy()))

    @staticmethod
    def _section(title: str) -> Gtk.Label:
        lbl = Gtk.Label(label=f"<b>{title}</b>", xalign=0)
        lbl.set_use_markup(True)
        return lbl
