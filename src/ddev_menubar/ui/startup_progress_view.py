from __future__ import annotations
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..models.startup_progress import ProgressKind, StartupProgress, StepStatus


class StartupProgressView(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_margin_start(10)
        self.set_margin_end(10)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        self._title_label = Gtk.Label(xalign=0)
        self._title_label.get_style_context().add_class("progress-step-active")
        self.pack_start(self._title_label, False, False, 0)

        self._steps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.pack_start(self._steps_box, False, False, 0)

        self._note_label = Gtk.Label(xalign=0)
        self._note_label.set_line_wrap(True)
        self._note_label.get_style_context().add_class("project-path")
        self.pack_start(self._note_label, False, False, 0)

    def update(self, progress: StartupProgress) -> None:
        self._title_label.set_text(progress.title)

        for child in self._steps_box.get_children():
            self._steps_box.remove(child)

        if progress.is_multi_project:
            for item in progress.projects:
                row = self._make_project_row(item)
                self._steps_box.pack_start(row, False, False, 0)
        else:
            for step in progress.steps:
                row = self._make_step_row(step)
                self._steps_box.pack_start(row, False, False, 0)

        if progress.note:
            self._note_label.set_text(progress.note)
            self._note_label.show()
        else:
            self._note_label.hide()

        self._steps_box.show_all()

    def _make_step_row(self, step) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.get_style_context().add_class("progress-step")

        icon = Gtk.Label()
        icon.set_size_request(16, -1)
        if step.status == StepStatus.COMPLETE:
            icon.set_text("✓")
            icon.get_style_context().add_class("progress-step-complete")
        elif step.status == StepStatus.ACTIVE:
            spinner = Gtk.Spinner()
            spinner.start()
            box.pack_start(spinner, False, False, 0)
        elif step.status == StepStatus.FAILED:
            icon.set_text("✗")
            icon.get_style_context().add_class("progress-step-failed")
        else:
            icon.set_text("·")
            icon.get_style_context().add_class("progress-step-pending")

        if step.status != StepStatus.ACTIVE:
            box.pack_start(icon, False, False, 0)

        label = Gtk.Label(label=step.label, xalign=0)
        if step.status == StepStatus.ACTIVE:
            label.get_style_context().add_class("progress-step-active")
        elif step.status == StepStatus.PENDING:
            label.get_style_context().add_class("progress-step-pending")
        elif step.status == StepStatus.COMPLETE:
            label.get_style_context().add_class("progress-step-complete")
        elif step.status == StepStatus.FAILED:
            label.get_style_context().add_class("progress-step-failed")
        box.pack_start(label, True, True, 0)
        return box

    def _make_project_row(self, item) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.get_style_context().add_class("progress-step")

        indicator = Gtk.Label()
        indicator.set_size_request(16, -1)
        if item.status == StepStatus.COMPLETE:
            indicator.set_text("✓")
            indicator.get_style_context().add_class("progress-step-complete")
        elif item.status == StepStatus.ACTIVE:
            spinner = Gtk.Spinner()
            spinner.start()
            box.pack_start(spinner, False, False, 0)
        elif item.status == StepStatus.FAILED:
            indicator.set_text("✗")
            indicator.get_style_context().add_class("progress-step-failed")
        else:
            indicator.set_text("·")
            indicator.get_style_context().add_class("progress-step-pending")

        if item.status != StepStatus.ACTIVE:
            box.pack_start(indicator, False, False, 0)

        name_label = Gtk.Label(label=item.name, xalign=0)
        name_label.get_style_context().add_class("project-name")
        box.pack_start(name_label, False, False, 0)

        status_label = Gtk.Label(label=item.label, xalign=0)
        status_label.get_style_context().add_class("project-path")
        box.pack_start(status_label, True, True, 0)
        return box
