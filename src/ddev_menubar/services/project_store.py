from __future__ import annotations
import re
import threading
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set

from gi.repository import GLib

from ..models.action_report import (
    DdevActionOutput, DdevActionReport, DdevLogExcerpt, DdevLogLine, DdevServiceIssue,
)
from ..models.group import DdevGroupStatus, DdevProjectGroup
from ..models.project import DdevProject, DdevProjectDetail
from ..models.startup_progress import DdevFriendlyLog, ProgressKind, StartupProgress
from .ddev_cli import DdevCLI, DdevCLIError
from .group_repository import ProjectGroupRepository
from .notification_service import NotificationService
from .preferences_repository import PreferencesRepository
from .terminal_launcher import TerminalLauncher


class DdevProjectStore:
    def __init__(
        self,
        cli: Optional[DdevCLI] = None,
        group_repo: Optional[ProjectGroupRepository] = None,
        notifications: Optional[NotificationService] = None,
        terminal: Optional[TerminalLauncher] = None,
        prefs_repo: Optional[PreferencesRepository] = None,
    ) -> None:
        self._cli = cli or DdevCLI()
        self._group_repo = group_repo or ProjectGroupRepository()
        self._notifications = notifications or NotificationService.shared()
        self._terminal = terminal or TerminalLauncher()
        self._prefs_repo = prefs_repo or PreferencesRepository()

        self.projects: List[DdevProject] = []
        self.groups: List[DdevProjectGroup] = self._group_repo.load()
        self.favourited_project_names: Set[str] = set(self._prefs_repo.load_favourites())
        self.selected_project_name: Optional[str] = None
        self.selected_detail: Optional[DdevProjectDetail] = None
        self.selected_group_id: Optional[str] = None
        self.is_editing_group: bool = False
        self.editing_group: Optional[DdevProjectGroup] = None
        self.is_loading: bool = False
        self.is_refreshing: bool = False
        self.is_performing_action: bool = False
        self.activity_message: Optional[str] = None
        self.status_message: Optional[str] = None
        self.last_refreshed: Optional[datetime] = None
        self.ddev_available: bool = self._cli.is_available
        self.startup_progress: Optional[StartupProgress] = None
        self.action_report: Optional[DdevActionReport] = None
        self.main_tab: str = "projects"
        self.search_text: str = ""
        self.group_search_text: str = ""
        self.mkcert_needs_install: bool = False

        self._listeners: List[Callable] = []
        self._refresh_in_progress: bool = False
        self._refresh_timer_id: Optional[int] = None

    @property
    def ddev_executable_path(self) -> Optional[str]:
        return self._cli.executable_path

    @property
    def running_count(self) -> int:
        return sum(1 for p in self.projects if p.is_running)

    @property
    def filtered_projects(self) -> List[DdevProject]:
        q = self.search_text.strip().lower()
        projects = self.projects if not q else [
            p for p in self.projects
            if q in p.name.lower() or q in p.shortroot.lower() or q in p.approot.lower()
        ]
        favs = [p for p in projects if p.name in self.favourited_project_names]
        rest = [p for p in projects if p.name not in self.favourited_project_names]
        return favs + rest

    def is_favourite(self, name: str) -> bool:
        return name in self.favourited_project_names

    def toggle_favourite(self, name: str) -> None:
        if name in self.favourited_project_names:
            self.favourited_project_names.discard(name)
        else:
            self.favourited_project_names.add(name)
        self._prefs_repo.save_favourites(sorted(self.favourited_project_names))
        self._emit()

    @property
    def filtered_groups(self) -> List[DdevProjectGroup]:
        q = self.group_search_text.strip().lower()
        if not q:
            return self.groups
        return [
            g for g in self.groups
            if q in g.name.lower() or any(q in n.lower() for n in g.project_names)
        ]

    @property
    def selected_project(self) -> Optional[DdevProject]:
        if not self.selected_project_name:
            return None
        return next((p for p in self.projects if p.name == self.selected_project_name), None)

    @property
    def selected_group(self) -> Optional[DdevProjectGroup]:
        if not self.selected_group_id:
            return None
        return next((g for g in self.groups if g.id == self.selected_group_id), None)

    def add_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable) -> None:
        self._listeners.discard(callback) if isinstance(self._listeners, set) else None
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _emit(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:
                pass

    def projects_in_group(self, group: DdevProjectGroup) -> List[DdevProject]:
        by_name = {p.name: p for p in self.projects}
        return [by_name[n] for n in group.project_names if n in by_name]

    def group_status(self, group: DdevProjectGroup) -> DdevGroupStatus:
        known = self.projects_in_group(group)
        known_names = {p.name for p in known}
        missing = sum(1 for n in group.project_names if n not in known_names)
        running = sum(1 for p in known if p.is_running)
        stopped = len(known) - running
        return DdevGroupStatus(running=running, stopped=stopped, missing=missing)

    def select_tab(self, tab: str) -> None:
        self.main_tab = tab
        if tab == "groups":
            self._clear_project_selection()
        else:
            self._clear_group_selection()
        self._emit()

    def select_project(self, name: Optional[str]) -> None:
        self.selected_project_name = name
        self.selected_detail = None
        self._clear_group_selection()
        self._emit()
        if name:
            self._load_detail_async(name)

    def select_group(self, group_id: Optional[str]) -> None:
        self.selected_group_id = group_id
        self.is_editing_group = False
        self.editing_group = None
        self._clear_project_selection()
        self._emit()

    def begin_create_group(self) -> None:
        self.selected_group_id = None
        self.is_editing_group = True
        self.editing_group = DdevProjectGroup(name="", project_names=[])
        self._clear_project_selection()
        self._emit()

    def duplicate_group(self, group: DdevProjectGroup) -> None:
        new_group = DdevProjectGroup(
            name=f"Copy of {group.name}",
            project_names=list(group.project_names),
        )
        self.selected_group_id = None
        self.is_editing_group = True
        self.editing_group = new_group
        self._clear_project_selection()
        self._emit()

    def begin_edit_group(self, group: DdevProjectGroup) -> None:
        self.selected_group_id = group.id
        self.is_editing_group = True
        self.editing_group = group
        self._clear_project_selection()
        self._emit()

    def cancel_group_editing(self) -> None:
        self.is_editing_group = False
        self.editing_group = None
        self._emit()

    def save_group(self, group: DdevProjectGroup) -> None:
        trimmed = group.name.strip()
        if not trimmed:
            self.status_message = "Group name is required."
            self._emit()
            return

        group.name = trimmed
        seen: Set[str] = set()
        group.project_names = [n for n in group.project_names if not (n in seen or seen.add(n))]

        existing_index = next(
            (i for i, g in enumerate(self.groups) if g.id == group.id), None
        )
        if existing_index is not None:
            self.groups[existing_index] = group
        else:
            self.groups.append(group)

        self.groups.sort(key=lambda g: g.name.lower())
        self._group_repo.save(self.groups)
        self.selected_group_id = group.id
        self.is_editing_group = False
        self.editing_group = None
        self.status_message = None
        self._emit()

    def delete_group(self, group: DdevProjectGroup) -> None:
        self.groups = [g for g in self.groups if g.id != group.id]
        self._group_repo.save(self.groups)
        if self.selected_group_id == group.id:
            self.selected_group_id = None
        self.is_editing_group = False
        self.editing_group = None
        self._emit()

    def start_auto_refresh(self, interval_seconds: int = 15) -> None:
        self._stop_auto_refresh()
        def tick():
            self.refresh_projects()
            return True
        self._refresh_timer_id = GLib.timeout_add_seconds(interval_seconds, tick)

    def stop_auto_refresh(self) -> None:
        self._stop_auto_refresh()

    def _stop_auto_refresh(self) -> None:
        if self._refresh_timer_id is not None:
            GLib.source_remove(self._refresh_timer_id)
            self._refresh_timer_id = None

    def refresh_projects(self, show_activity: bool = False) -> None:
        self.ddev_available = self._cli.is_available
        if not self.ddev_available:
            self.status_message = "DDEV not found. Install DDEV or ensure it is in your PATH."
            self.projects = []
            self.activity_message = None
            self._emit()
            return

        if self._refresh_in_progress:
            return

        is_initial = not self.projects
        self._refresh_in_progress = True
        if is_initial:
            self.is_loading = True
        else:
            self.is_refreshing = True
            if show_activity:
                self.activity_message = "Refreshing projects…"
        self._emit()

        def worker():
            try:
                fetched = self._cli.list_projects()
                mkcert_issue = DdevCLI.mkcert_needs_install()
                def on_main():
                    self._refresh_in_progress = False
                    self.is_loading = False
                    self.is_refreshing = False
                    if fetched != self.projects:
                        self.projects = fetched
                    self.last_refreshed = datetime.now()
                    self.mkcert_needs_install = mkcert_issue
                    if show_activity:
                        self.activity_message = None
                    if self.selected_project_name:
                        if not any(p.name == self.selected_project_name for p in self.projects):
                            self.selected_project_name = None
                            self.selected_detail = None
                        else:
                            self._load_detail_async(self.selected_project_name)
                    self._emit()
                    return False
                GLib.idle_add(on_main)
            except Exception as e:
                def on_error():
                    self._refresh_in_progress = False
                    self.is_loading = False
                    self.is_refreshing = False
                    if show_activity:
                        self.activity_message = None
                    self.status_message = str(e)
                    self._emit()
                    return False
                GLib.idle_add(on_error)

        threading.Thread(target=worker, daemon=True).start()

    def _load_detail_async(self, name: str) -> None:
        def worker():
            try:
                detail = self._cli.describe_project(name)
                def on_main():
                    if self.selected_project_name == name:
                        self.selected_detail = detail
                    self._emit()
                    return False
                GLib.idle_add(on_main)
            except Exception as e:
                def on_error():
                    self.status_message = str(e)
                    self._emit()
                    return False
                GLib.idle_add(on_error)

        threading.Thread(target=worker, daemon=True).start()

    def start_project(self, name: str) -> None:
        self._perform_project_action(
            f"Starting {name}…",
            [name],
            ProgressKind.START,
            lambda on_line: self._cli.start_project(name, on_line),
        )

    def stop_project(self, name: str) -> None:
        self._perform_project_action(
            f"Stopping {name}…",
            [name],
            ProgressKind.STOP,
            lambda on_line: self._cli.stop_project(name, on_line),
        )

    def restart_project(self, name: str) -> None:
        self._perform_project_action(
            f"Restarting {name}…",
            [name],
            ProgressKind.RESTART,
            lambda on_line: self._cli.restart_project(name, on_line),
        )

    def set_xdebug(self, name: str, enabled: bool) -> None:
        label = f"Enabling Xdebug for {name}…" if enabled else f"Disabling Xdebug for {name}…"
        self.is_performing_action = True
        self.activity_message = label
        self.status_message = None
        self._emit()

        def worker():
            try:
                self._cli.set_xdebug(name, enabled)
                def on_done():
                    self.is_performing_action = False
                    self.activity_message = None
                    self.refresh_projects()
                    return False
                GLib.idle_add(on_done)
            except Exception as e:
                def on_error():
                    self.is_performing_action = False
                    self.activity_message = None
                    self.status_message = str(e)
                    self._emit()
                    return False
                GLib.idle_add(on_error)

        threading.Thread(target=worker, daemon=True).start()

    def start_group(self, group: DdevProjectGroup) -> None:
        names = [p.name for p in self.projects_in_group(group) if not p.is_running]
        if not names:
            self.status_message = f"All projects in {group.name} are already running."
            self._emit()
            return
        self._perform_project_action(
            f"Starting {group.name}…",
            names,
            ProgressKind.START,
            lambda on_line: self._cli.start_projects_parallel(names, on_line),
        )

    def stop_group(self, group: DdevProjectGroup) -> None:
        names = [p.name for p in self.projects_in_group(group) if p.is_running]
        if not names:
            self.status_message = f"No running projects in {group.name}."
            self._emit()
            return
        self._perform_project_action(
            f"Stopping {group.name}…",
            names,
            ProgressKind.STOP,
            lambda on_line: self._cli.stop_projects_parallel(names, on_line),
        )

    def restart_group(self, group: DdevProjectGroup) -> None:
        names = [n for n in group.project_names if any(p.name == n for p in self.projects)]
        if not names:
            self.status_message = f"No known projects in {group.name}."
            self._emit()
            return
        self._perform_project_action(
            f"Restarting {group.name}…",
            names,
            ProgressKind.RESTART,
            lambda on_line: self._cli.restart_projects_parallel(names, on_line),
        )

    def open_url(self, url: str) -> None:
        import subprocess
        subprocess.Popen(["xdg-open", url], start_new_session=True)

    def open_primary_url(self, project: DdevProject) -> None:
        url = project.primary_url or project.httpsurl or project.httpurl
        if url:
            self.open_url(url)

    def open_mailpit(self, project: DdevProject) -> None:
        if project.mailpit_url:
            self.open_url(project.mailpit_url)

    def reveal_in_files(self, project: DdevProject) -> None:
        import subprocess
        subprocess.Popen(["xdg-open", project.approot], start_new_session=True)

    def ssh_into_project(self, name: str, approot: str) -> None:
        try:
            q = self._shell_quote(name)
            self._terminal.open(f"ddev ssh {q}", working_directory=approot)
            self.status_message = None
        except Exception as e:
            self.status_message = str(e)
        self._emit()

    def auth_ssh_in_terminal(self) -> None:
        try:
            self._terminal.open("ddev auth ssh")
            self.status_message = None
        except Exception as e:
            self.status_message = str(e)
        self._emit()

    def fix_mkcert(self) -> None:
        import shutil
        import subprocess
        self.activity_message = "Running mkcert -install…"
        self.status_message = None
        self._emit()

        def worker():
            try:
                mkcert_bin = shutil.which("mkcert") or "mkcert"
                result = subprocess.run(
                    [mkcert_bin, "-install"],
                    capture_output=True, text=True, timeout=30,
                    env=self._cli._env(),
                )
                rechk = DdevCLI.mkcert_needs_install()

                def on_done():
                    self.activity_message = None
                    self.mkcert_needs_install = rechk
                    if result.returncode != 0:
                        out = (result.stderr + result.stdout).strip()
                        self.status_message = out or "mkcert -install failed."
                    else:
                        self.status_message = None
                    self._emit()
                    return False
                GLib.idle_add(on_done)
            except Exception as e:
                def on_error():
                    self.activity_message = None
                    self.status_message = str(e)
                    self._emit()
                    return False
                GLib.idle_add(on_error)

        threading.Thread(target=worker, daemon=True).start()

    def show_logs_in_terminal(self, name: str, approot: str) -> None:
        try:
            q = self._shell_quote(name)
            self._terminal.open(f"ddev logs -f {q}", working_directory=approot)
            self.status_message = None
        except Exception as e:
            self.status_message = str(e)
        self._emit()

    def dismiss_action_report(self) -> None:
        self.action_report = None
        self._emit()

    def open_project_from_group(self, name: str) -> None:
        self.main_tab = "projects"
        self._clear_group_selection()
        self.select_project(name)

    def _clear_project_selection(self) -> None:
        self.selected_project_name = None
        self.selected_detail = None

    def _clear_group_selection(self) -> None:
        self.selected_group_id = None
        self.is_editing_group = False
        self.editing_group = None

    def _perform_project_action(
        self,
        title: str,
        project_names: List[str],
        kind: ProgressKind,
        action_fn,
    ) -> None:
        self.is_performing_action = True
        self.activity_message = None
        self.status_message = None
        self.action_report = None
        self.startup_progress = DdevFriendlyLog.initial_progress(
            title=title.rstrip("…"),
            project_names=project_names,
            kind=kind,
        )
        self._emit()

        def on_log_line(line: DdevLogLine) -> None:
            def update():
                if self.startup_progress:
                    DdevFriendlyLog.apply(line, self.startup_progress)
                    self._emit()
                return False
            GLib.idle_add(update)

        def worker():
            try:
                output: DdevActionOutput = action_fn(on_log_line)

                def on_done():
                    if self.startup_progress and not self.startup_progress.is_finished:
                        DdevFriendlyLog.mark_remaining_complete(self.startup_progress)

                    if DdevCLI.mkcert_warning_in_lines(output.lines):
                        self.mkcert_needs_install = True

                    if kind == ProgressKind.STOP:
                        if output.errors:
                            self.status_message = "\n".join(output.errors)
                        else:
                            self.status_message = None
                            self.activity_message = None
                        self.is_performing_action = False
                        self.startup_progress = None
                        self._emit()
                        self.refresh_projects()
                        return False

                    self.activity_message = "Updating projects…"
                    self._emit()

                    def after_refresh():
                        self.is_performing_action = False
                        issues, messages, hints = self._post_action_check(project_names, output)

                        if issues or messages:
                            self.action_report = DdevActionReport(
                                title=f"{title.rstrip('…')} - issues detected",
                                project_names=project_names,
                                messages=messages,
                                service_issues=issues,
                                log_excerpts=[],
                                hints=sorted(set(hints)),
                            )
                            self.status_message = self._summarize(issues, messages)
                        else:
                            self.status_message = None
                            self.activity_message = None
                            self.startup_progress = None

                        self._notify_based_on_state(project_names, kind, self.status_message)
                        self._emit()
                        return False

                    def do_refresh():
                        self.refresh_projects()
                        GLib.timeout_add(500, after_refresh)
                        return False

                    GLib.idle_add(do_refresh)
                    return False

                GLib.idle_add(on_done)

            except Exception as e:
                def on_error():
                    self.is_performing_action = False
                    self.activity_message = None
                    if self.startup_progress:
                        DdevFriendlyLog.apply(DdevLogLine("error", str(e)), self.startup_progress)
                    self.status_message = str(e)
                    self._notify_based_on_state(project_names, kind, str(e))
                    self.refresh_projects()
                    self._emit()
                    return False
                GLib.idle_add(on_error)

        threading.Thread(target=worker, daemon=True).start()

    def _post_action_check(self, project_names, output) -> tuple:
        messages = list(output.errors)
        issues: List[DdevServiceIssue] = []
        hints = []
        mutagen_problems = False

        for name in project_names:
            project = next((p for p in self.projects if p.name == name), None)
            if project and project.mutagen_status and self._mutagen_unhealthy(project.mutagen_status):
                mutagen_problems = True
                messages.append(f"{name}: Mutagen - {project.mutagen_status}")

            try:
                detail = self._cli.describe_project(name)
                if not self._cli.project_looks_healthy(detail):
                    messages.append(f"{name}: status is {detail.status_desc}")
                issues.extend(self._cli.service_issues(detail))
            except Exception:
                pass

        combined = " ".join(messages + [f"{i.service_name} {i.status}" for i in issues]).lower()

        if "ssh" in combined or "keychain" in combined or "agent" in combined:
            hints.append("Try Auth SSH (loads keys into ddev-ssh-agent).")
        if mutagen_problems:
            hints.append("Mutagen issues can pause projects - try `ddev mutagen st <project>`.")
        if any(i.status == "exited" for i in issues):
            hints.append("A container exited after start - check the service logs below.")
        if issues:
            hints.append("DDEV may report success even when a service fails - inspect logs.")

        return issues, messages, hints

    def _summarize(self, issues: List[DdevServiceIssue], messages: List[str]) -> str:
        if issues:
            i = issues[0]
            return f"{i.project_name}: {i.service_name} is {i.status}"
        if messages:
            return messages[0].split("\n")[0][:180]
        return "Start completed with issues."

    def _notify_based_on_state(
        self, project_names: List[str], kind: ProgressKind, failure_msg: Optional[str]
    ) -> None:
        if kind == ProgressKind.STOP:
            return

        running = [n for n in project_names if any(p.name == n and p.is_running for p in self.projects)]
        not_running = [n for n in project_names if n not in running]
        restarted = kind == ProgressKind.RESTART

        url = None
        if self.startup_progress and self.startup_progress.note:
            match = re.search(r"https?://\S+", self.startup_progress.note)
            if match:
                url = match.group(0)
        if not url:
            for name in project_names:
                p = next((p for p in self.projects if p.name == name), None)
                if p and p.primary_url:
                    url = p.primary_url
                    break

        if not not_running:
            self._notifications.notify_projects_ready(project_names, restarted, url)
        elif not running:
            self._notifications.notify_projects_failed(
                not_running, restarted, failure_msg or "Project failed to start."
            )
        else:
            self._notifications.notify_projects_ready(running, restarted, url)
            self._notifications.notify_projects_failed(
                not_running, restarted, failure_msg or "Some projects failed to start."
            )

    @staticmethod
    def _mutagen_unhealthy(status: str) -> bool:
        n = status.lower()
        return "fail" in n or "error" in n or "nosession" in n

    @staticmethod
    def _shell_quote(s: str) -> str:
        return "'" + s.replace("'", "'\\''") + "'"
