from __future__ import annotations
import json
import os
import shutil
import subprocess
import threading
from typing import Callable, Iterator, List, Optional, Tuple

from ..models.action_report import DdevActionOutput, DdevLogLine, DdevServiceIssue
from ..models.project import DdevProject, DdevProjectDetail
from ..models.startup_progress import DdevFriendlyLog, StartupProgress


_OPTIONAL_ADD_ON_SERVICES = {"xhgui", "phpmyadmin"}

_MKCERT_WARNING = "mkcert may not be properly installed"


class DdevCLIError(Exception):
    pass


class DdevCLI:
    def __init__(self, ddev_path: Optional[str] = None):
        self._path = ddev_path or DdevCLI._locate_ddev()

    @property
    def is_available(self) -> bool:
        return self._path is not None

    @property
    def executable_path(self) -> Optional[str]:
        return self._path

    def list_projects(self) -> List[DdevProject]:
        data = self._run_json(["list", "-j"])
        raw = data.get("raw", data)
        if isinstance(raw, list):
            projects = [DdevProject.from_dict(p) for p in raw]
        else:
            projects = []
        return sorted(
            projects,
            key=lambda p: (not p.is_running, p.name.lower()),
        )

    def describe_project(self, name: str) -> DdevProjectDetail:
        data = self._run_json(["describe", name, "-j"])
        raw = data.get("raw", data)
        return DdevProjectDetail.from_dict(raw)

    def version_info(self) -> dict:
        data = self._run_json(["version", "-j"])
        return data.get("raw", data)

    def start_project(self, name: str, on_line: Optional[Callable[[DdevLogLine], None]] = None) -> DdevActionOutput:
        return self._run_action(["start", name, "-j", "-y"], on_line)

    def stop_project(self, name: str, on_line: Optional[Callable[[DdevLogLine], None]] = None) -> DdevActionOutput:
        return self._run_action(["stop", name, "-j"], on_line)

    def restart_project(self, name: str, on_line: Optional[Callable[[DdevLogLine], None]] = None) -> DdevActionOutput:
        return self._run_action(["restart", name, "-j", "-y"], on_line)

    def set_xdebug(self, project_name: str, enabled: bool) -> None:
        self._run_raw(["xdebug", "on" if enabled else "off", project_name, "-j", "-y"])

    def logs_snippet(self, project_name: str, service: str, tail: int = 30) -> str:
        result = self._run_process(["logs", project_name, "-s", service, "--tail", str(tail)])
        return result.strip()

    def stream_container_logs(
        self,
        project_name: str,
        service: str = "web",
        follow: bool = True,
        tail: str = "100",
    ) -> subprocess.Popen:
        args = ["logs", project_name]
        if follow:
            args.append("-f")
        if tail:
            args.extend(["--tail", tail])
        if service != "web":
            args.extend(["-s", service])
        return self._open_streaming_process(args)

    def stream_file_log(
        self,
        project_name: str,
        path: str,
        service: str = "web",
        follow: bool = True,
        tail: str = "100",
    ) -> subprocess.Popen:
        tail_args = ["tail"]
        if follow:
            tail_args.append("-f")
        if tail:
            tail_args.extend(["-n", tail])
        tail_args.append(path)
        args = ["exec", "-p", project_name, "-s", service, "--"] + tail_args
        return self._open_streaming_process(args)

    def start_projects_parallel(
        self, names: List[str], on_line: Optional[Callable[[DdevLogLine], None]] = None
    ) -> DdevActionOutput:
        return self._run_parallel("start", names, on_line)

    def stop_projects_parallel(
        self, names: List[str], on_line: Optional[Callable[[DdevLogLine], None]] = None
    ) -> DdevActionOutput:
        return self._run_parallel("stop", names, on_line)

    def restart_projects_parallel(
        self, names: List[str], on_line: Optional[Callable[[DdevLogLine], None]] = None
    ) -> DdevActionOutput:
        return self._run_parallel("restart", names, on_line)

    def service_issues(self, detail: DdevProjectDetail) -> List[DdevServiceIssue]:
        if not detail.services:
            return []
        issues = []
        for name, info in detail.services.items():
            if info.status and info.status != "running":
                if self._should_ignore_non_running(name, detail):
                    continue
                issues.append(DdevServiceIssue(detail.name, name, info.status))
        return issues

    def project_looks_healthy(self, detail: DdevProjectDetail) -> bool:
        if detail.status != "running":
            return False
        status_desc = detail.status_desc.lower()
        if any(x in status_desc for x in ("unhealthy", "paused", "stopped")):
            return False
        return not self.service_issues(detail)

    def _should_ignore_non_running(self, name: str, detail: DdevProjectDetail) -> bool:
        n = name.lower()
        if n in _OPTIONAL_ADD_ON_SERVICES:
            return True
        if n == "db":
            return not detail.includes_database_service
        return False

    def _run_parallel(
        self, command: str, names: List[str], on_line: Optional[Callable[[DdevLogLine], None]]
    ) -> DdevActionOutput:
        results: list = [None] * len(names)
        errors: list = [None] * len(names)
        lock = threading.Lock()

        def worker(index: int, name: str) -> None:
            def prefix_line(line: DdevLogLine) -> None:
                if on_line:
                    on_line(DdevLogLine(line.level, f"[{name}] {line.message}"))

            try:
                args = self._args_for(command, name)
                output = self._run_action(args, prefix_line if on_line else None)
                with lock:
                    results[index] = output
            except Exception as e:
                msg = str(e)
                if on_line:
                    on_line(DdevLogLine("error", f"[{name}] {msg}"))
                with lock:
                    errors[index] = msg

        threads = [
            threading.Thread(target=worker, args=(i, n), daemon=True)
            for i, n in enumerate(names)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        all_lines: List[DdevLogLine] = []
        all_output = ""
        failure_msgs = []

        for i, name in enumerate(names):
            if results[i] is not None:
                all_lines.extend(results[i].lines)
                all_output += results[i].raw_output
            elif errors[i]:
                failure_msgs.append(f"{name}: {errors[i]}")
                all_lines.append(DdevLogLine("error", f"[{name}] {errors[i]}"))

        if len(failure_msgs) == len(names):
            raise DdevCLIError("\n".join(failure_msgs))

        return DdevActionOutput(
            exit_code=0 if not failure_msgs else 1,
            lines=all_lines,
            raw_output=all_output,
        )

    @staticmethod
    def _args_for(command: str, name: str) -> List[str]:
        if command in ("start", "restart"):
            return [command, name, "-j", "-y"]
        return [command, name, "-j"]

    def _run_action(
        self, args: List[str], on_line: Optional[Callable[[DdevLogLine], None]]
    ) -> DdevActionOutput:
        if not self._path:
            raise DdevCLIError("DDEV not found.")

        process = subprocess.Popen(
            [self._path] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._env(),
            text=True,
        )

        all_output = ""
        parsed_lines: List[DdevLogLine] = []

        def read_stream(stream) -> None:
            nonlocal all_output
            for raw_line in stream:
                all_output += raw_line
                log_line = DdevCLI._parse_ndjson_line(raw_line.rstrip("\n"))
                if log_line:
                    parsed_lines.append(log_line)
                    if on_line:
                        on_line(log_line)

        stdout_thread = threading.Thread(target=read_stream, args=(process.stdout,), daemon=True)
        stderr_thread = threading.Thread(target=read_stream, args=(process.stderr,), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        stdout_thread.join()
        stderr_thread.join()
        process.wait()

        if process.returncode != 0:
            raise DdevCLIError(
                DdevCLI._format_action_failure(all_output, parsed_lines, process.returncode)
            )

        return DdevActionOutput(
            exit_code=process.returncode, lines=parsed_lines, raw_output=all_output
        )

    def _run_json(self, args: List[str]) -> dict:
        if not self._path:
            raise DdevCLIError("DDEV not found.")
        raw = self._run_process(args)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise DdevCLIError(f"Could not parse DDEV response: {e}") from e

    def _run_raw(self, args: List[str]) -> str:
        if not self._path:
            raise DdevCLIError("DDEV not found.")
        return self._run_process(args)

    def _run_process(self, args: List[str]) -> str:
        if not self._path:
            raise DdevCLIError("DDEV not found.")
        result = subprocess.run(
            [self._path] + args,
            capture_output=True,
            text=True,
            env=self._env(),
        )
        if result.returncode != 0:
            output = (result.stderr + result.stdout).strip()
            raise DdevCLIError(output or f"DDEV command failed (exit {result.returncode})")
        return result.stdout

    def _open_streaming_process(self, args: List[str]) -> subprocess.Popen:
        if not self._path:
            raise DdevCLIError("DDEV not found.")
        return subprocess.Popen(
            [self._path] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=self._env(),
            bufsize=0,
        )

    def _env(self) -> dict:
        env = os.environ.copy()
        env["DDEV_NO_TUI"] = "true"
        home = os.path.expanduser("~")
        extra_paths = [
            "/usr/local/bin",
            "/usr/bin",
            f"{home}/.ddev/bin",
            f"{home}/bin",
            f"{home}/.local/bin",
        ]
        existing = env.get("PATH", "").split(":")
        seen = set()
        new_path = []
        for p in extra_paths + existing:
            if p and p not in seen:
                seen.add(p)
                new_path.append(p)
        env["PATH"] = ":".join(new_path)
        return env

    @staticmethod
    def _parse_ndjson_line(line: str) -> Optional[DdevLogLine]:
        line = line.strip()
        if not line:
            return None
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and "level" in obj and "msg" in obj:
                return DdevLogLine(level=obj["level"], message=obj["msg"])
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    @staticmethod
    def _format_action_failure(
        raw_output: str, lines: List[DdevLogLine], exit_code: int
    ) -> str:
        error_msgs = [l.message for l in lines if l.level in ("error", "fatal", "warning")]
        if error_msgs:
            return "\n".join(error_msgs)
        if raw_output.strip():
            return raw_output.strip()
        return f"DDEV command failed with exit code {exit_code}."

    @staticmethod
    def mkcert_needs_install() -> bool:
        """True when mkcert is present but its CA is not in the system trust store."""
        import glob
        if not shutil.which("mkcert"):
            return False
        try:
            r = subprocess.run(
                ["mkcert", "-CAROOT"], capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0:
                return False
            caroot = r.stdout.strip()
            if not os.path.isfile(os.path.join(caroot, "rootCA.pem")):
                # CA hasn't been created yet - mkcert -install will create and trust it.
                return True
            # Check system-wide trust (Debian/Ubuntu path).
            if glob.glob("/usr/local/share/ca-certificates/mkcert*.crt"):
                return False
            # Check p11-kit trust anchors (Arch, Fedora, etc.).
            if glob.glob("/etc/ca-certificates/trust-source/anchors/mkcert*.pem"):
                return False
            # Check NSS database used by Firefox / Chromium.
            nssdb = os.path.expanduser("~/.pki/nssdb")
            if os.path.isdir(nssdb) and shutil.which("certutil"):
                r2 = subprocess.run(
                    ["certutil", "-d", f"sql:{nssdb}", "-L"],
                    capture_output=True, text=True, timeout=5,
                )
                if "mkcert" in r2.stdout.lower():
                    return False
            return True
        except Exception:
            return False

    @staticmethod
    def mkcert_warning_in_lines(lines: list) -> bool:
        return any(_MKCERT_WARNING in l.message for l in lines)

    @staticmethod
    def _locate_ddev() -> Optional[str]:
        home = os.path.expanduser("~")
        candidates = [
            "/usr/local/bin/ddev",
            f"{home}/.ddev/bin/ddev",
            f"{home}/.local/bin/ddev",
            "/usr/bin/ddev",
        ]
        for path in candidates:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return shutil.which("ddev")
