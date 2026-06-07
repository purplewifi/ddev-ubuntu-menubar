from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


class StepStatus(Enum):
    PENDING = auto()
    ACTIVE = auto()
    COMPLETE = auto()
    WARNING = auto()
    FAILED = auto()


class ProgressKind(Enum):
    START = auto()
    RESTART = auto()
    STOP = auto()


@dataclass
class StartupStep:
    id: str
    label: str
    status: StepStatus


@dataclass
class ProjectProgressItem:
    name: str
    label: str
    status: StepStatus


@dataclass
class StartupProgress:
    kind: ProgressKind
    title: str
    project_names: List[str]
    projects: List[ProjectProgressItem]
    steps: List[StartupStep]
    note: Optional[str] = None
    is_finished: bool = False
    succeeded: bool = False

    @property
    def is_multi_project(self) -> bool:
        return len(self.project_names) > 1

    @property
    def completed_count(self) -> int:
        return sum(1 for p in self.projects if p.status == StepStatus.COMPLETE)

    @property
    def active_step(self) -> Optional[StartupStep]:
        for step in reversed(self.steps):
            if step.status == StepStatus.ACTIVE:
                return step
        return None


_STEP_ORDER = ["prepare", "build", "services", "sync", "router", "ready"]


class DdevFriendlyLog:
    @staticmethod
    def initial_progress(
        title: str,
        project_names: List[str],
        kind: ProgressKind,
    ) -> StartupProgress:
        if len(project_names) > 1:
            return StartupProgress(
                kind=kind,
                title=title,
                project_names=project_names,
                projects=[
                    ProjectProgressItem(name=n, label="Waiting", status=StepStatus.PENDING)
                    for n in project_names
                ],
                steps=[],
                note=DdevFriendlyLog._summary_note(kind, 0, len(project_names)),
            )

        return StartupProgress(
            kind=kind,
            title=title,
            project_names=project_names,
            projects=[],
            steps=DdevFriendlyLog._initial_steps(kind),
        )

    @staticmethod
    def mark_remaining_complete(progress: StartupProgress) -> None:
        if progress.is_multi_project:
            label = DdevFriendlyLog._finished_label(progress.kind)
            for item in progress.projects:
                if item.status != StepStatus.FAILED:
                    item.status = StepStatus.COMPLETE
                    item.label = label
            DdevFriendlyLog._refresh_overall_status(progress)
            return
        DdevFriendlyLog._mark_success(progress, DdevFriendlyLog._finished_label(progress.kind))

    @staticmethod
    def apply(line, progress: StartupProgress) -> None:
        project_name, message = DdevFriendlyLog._extract_project_and_message(line.message)

        if progress.is_multi_project:
            if project_name:
                DdevFriendlyLog._apply_to_project(project_name, line, message, progress)
            return

        DdevFriendlyLog._apply_to_single(line, message, progress)

    @staticmethod
    def _apply_to_project(
        name: str, line, message: str, progress: StartupProgress
    ) -> None:
        item = next((p for p in progress.projects if p.name == name), None)
        if item is None:
            return

        normalized = message.lower()

        if line.level in ("error", "fatal"):
            item.status = StepStatus.FAILED
            item.label = DdevFriendlyLog._first_sentence(message)
            DdevFriendlyLog._refresh_overall_status(progress)
            return

        if progress.kind == ProgressKind.STOP:
            if "has been stopped" in normalized:
                item.label, item.status = "Stopped", StepStatus.COMPLETE
            elif "stopping" in normalized or "removed" in normalized:
                item.label, item.status = "Stopping", StepStatus.ACTIVE
            elif item.status == StepStatus.PENDING:
                item.label, item.status = "Stopping", StepStatus.ACTIVE
        else:
            if "successfully started" in normalized or "successfully restarted" in normalized:
                item.label, item.status = "Ready", StepStatus.COMPLETE
            elif "your project can be reached at" in normalized:
                item.label, item.status = "Ready", StepStatus.COMPLETE
            elif "mutagen" in normalized:
                item.label, item.status = "Syncing files", StepStatus.ACTIVE
            elif "building project images" in normalized:
                item.label, item.status = "Building", StepStatus.ACTIVE
            elif "container" in normalized and "started" in normalized:
                item.label, item.status = "Starting services", StepStatus.ACTIVE
            elif "starting" in normalized:
                item.label, item.status = "Getting ready", StepStatus.ACTIVE
            elif "router" in normalized:
                item.label, item.status = "Connecting router", StepStatus.ACTIVE
            elif item.status == StepStatus.PENDING:
                item.label, item.status = "Getting ready", StepStatus.ACTIVE

        DdevFriendlyLog._refresh_overall_status(progress)

    @staticmethod
    def _apply_to_single(line, message: str, progress: StartupProgress) -> None:
        normalized = message.lower()

        if line.level in ("error", "fatal"):
            DdevFriendlyLog._fail_current_step(progress)
            progress.note = DdevFriendlyLog._first_sentence(message)
            return

        if line.level == "warning":
            note = DdevFriendlyLog._friendly_warning(message)
            if note:
                progress.note = note

        if progress.kind == ProgressKind.STOP:
            if "has been stopped" in normalized:
                DdevFriendlyLog._mark_success(progress, "Stopped")
            elif "stopping" in normalized or "removed" in normalized:
                DdevFriendlyLog._activate(progress, "prepare", "Stopping containers")
            return

        if "starting" in normalized and normalized.endswith("..."):
            DdevFriendlyLog._activate(progress, "prepare", "Getting ready")
            return
        if "building project images" in normalized:
            DdevFriendlyLog._activate(progress, "build", "Building containers")
            return
        if "project images built" in normalized:
            DdevFriendlyLog._complete(progress, "build")
            return
        if "container" in normalized and "-db" in normalized and "started" in normalized:
            DdevFriendlyLog._complete(progress, "build")
            DdevFriendlyLog._activate(progress, "services", "Starting database")
            return
        if "container" in normalized and "-web" in normalized and "started" in normalized:
            DdevFriendlyLog._complete(progress, "services")
            return
        if "mutagen" in normalized:
            DdevFriendlyLog._activate(progress, "sync", "Syncing your files")
            if "completed" in normalized or "flush completed" in normalized:
                DdevFriendlyLog._complete(progress, "sync")
            return
        if "web_extra_daemons" in normalized or "extra_daemons" in normalized:
            DdevFriendlyLog._activate(progress, "services", "Starting background services")
            return
        if "ddev-router" in normalized or "router" in normalized:
            DdevFriendlyLog._activate(progress, "router", "Connecting router")
            if "started" in normalized:
                DdevFriendlyLog._complete(progress, "router")
            return
        if "successfully started" in normalized or "successfully restarted" in normalized:
            DdevFriendlyLog._mark_success(progress, "Ready to go")
            return
        if "your project can be reached at" in normalized:
            DdevFriendlyLog._mark_success(progress, "Ready to go")
            url = DdevFriendlyLog._extract_url(message)
            if url:
                progress.note = f"Ready at {url}"
            return

        if line.level == "info":
            friendly = DdevFriendlyLog._friendly_info(message)
            if friendly:
                DdevFriendlyLog._update_active_label(progress, friendly)

    @staticmethod
    def _refresh_overall_status(progress: StartupProgress) -> None:
        total = len(progress.projects)
        completed = sum(1 for p in progress.projects if p.status == StepStatus.COMPLETE)
        failed = any(p.status == StepStatus.FAILED for p in progress.projects)
        all_done = all(p.status in (StepStatus.COMPLETE, StepStatus.FAILED) for p in progress.projects)

        if all_done:
            progress.is_finished = True
            progress.succeeded = not failed and completed == total
            if progress.succeeded:
                progress.note = DdevFriendlyLog._finished_note(progress.kind, completed)
            else:
                progress.note = f"{completed} of {total} finished"
        else:
            progress.note = DdevFriendlyLog._summary_note(progress.kind, completed, total)

    @staticmethod
    def _initial_steps(kind: ProgressKind) -> List[StartupStep]:
        if kind == ProgressKind.STOP:
            return [
                StartupStep("prepare", "Stopping containers", StepStatus.ACTIVE),
                StartupStep("ready", "Finishing up", StepStatus.PENDING),
            ]
        return [
            StartupStep("prepare", "Getting ready", StepStatus.ACTIVE),
            StartupStep("build", "Building containers", StepStatus.PENDING),
            StartupStep("services", "Starting services", StepStatus.PENDING),
            StartupStep("sync", "Syncing files", StepStatus.PENDING),
            StartupStep("router", "Connecting router", StepStatus.PENDING),
            StartupStep("ready", "Finishing up", StepStatus.PENDING),
        ]

    @staticmethod
    def _summary_note(kind: ProgressKind, completed: int, total: int) -> str:
        if kind == ProgressKind.STOP:
            return f"{completed} of {total} stopped"
        return f"{completed} of {total} ready"

    @staticmethod
    def _finished_label(kind: ProgressKind) -> str:
        return "Stopped" if kind == ProgressKind.STOP else "Ready"

    @staticmethod
    def _finished_note(kind: ProgressKind, count: int) -> str:
        if kind == ProgressKind.STOP:
            return "Project stopped" if count == 1 else f"All {count} projects stopped"
        return "Project ready" if count == 1 else f"All {count} projects ready"

    @staticmethod
    def _mark_success(progress: StartupProgress, label: str) -> None:
        for step in progress.steps:
            if step.status in (StepStatus.ACTIVE, StepStatus.PENDING):
                step.status = StepStatus.COMPLETE
        ready = next((s for s in progress.steps if s.id == "ready"), None)
        if ready:
            ready.label = label
            ready.status = StepStatus.COMPLETE
        progress.is_finished = True
        progress.succeeded = True

    @staticmethod
    def _fail_current_step(progress: StartupProgress) -> None:
        for step in reversed(progress.steps):
            if step.status == StepStatus.ACTIVE:
                step.status = StepStatus.FAILED
                progress.is_finished = True
                progress.succeeded = False
                return
        for step in progress.steps:
            if step.status == StepStatus.PENDING:
                step.status = StepStatus.FAILED
                progress.is_finished = True
                progress.succeeded = False
                return

    @staticmethod
    def _activate(progress: StartupProgress, step_id: str, label: str) -> None:
        DdevFriendlyLog._complete_earlier_steps(progress, step_id)
        for step in progress.steps:
            if step.id == step_id:
                step.label = label
                step.status = StepStatus.ACTIVE
                return

    @staticmethod
    def _complete(progress: StartupProgress, step_id: str, label: Optional[str] = None) -> None:
        for step in progress.steps:
            if step.id == step_id:
                if label:
                    step.label = label
                step.status = StepStatus.COMPLETE
                return

    @staticmethod
    def _complete_earlier_steps(progress: StartupProgress, before_id: str) -> None:
        if before_id not in _STEP_ORDER:
            return
        target_index = _STEP_ORDER.index(before_id)
        for step_id in _STEP_ORDER[:target_index]:
            for step in progress.steps:
                if step.id == step_id and step.status != StepStatus.COMPLETE:
                    step.status = StepStatus.COMPLETE

    @staticmethod
    def _update_active_label(progress: StartupProgress, label: str) -> None:
        for step in reversed(progress.steps):
            if step.status == StepStatus.ACTIVE:
                step.label = label
                return

    @staticmethod
    def _extract_project_and_message(message: str):
        if message.startswith("["):
            end = message.find("]")
            if end != -1:
                name = message[1:end]
                rest = message[end + 1:].strip()
                return name, rest
        return None, message

    @staticmethod
    def _friendly_info(message: str) -> Optional[str]:
        n = message.lower()
        if "network" in n and "created" in n:
            return "Setting up network"
        if "waiting" in n:
            return "Waiting for services"
        if "pulling" in n:
            return "Pulling images"
        return None

    @staticmethod
    def _friendly_warning(message: str) -> Optional[str]:
        n = message.lower()
        if "mutagen" in n and "upload_dirs" in n:
            return "Tip: configuring upload folders can speed up startup."
        if "custom configuration detected" in n:
            return "This project has custom DDEV settings."
        return DdevFriendlyLog._first_sentence(message, max_length=120)

    @staticmethod
    def _first_sentence(message: str, max_length: int = 180) -> str:
        line = message.split("\n")[0].strip()
        if len(line) <= max_length:
            return line
        return line[:max_length - 1] + "…"

    @staticmethod
    def _extract_url(message: str) -> Optional[str]:
        match = re.search(r"https?://[^\s\\]+", message)
        return match.group(0) if match else None
