from __future__ import annotations
import os
import shlex
import shutil
import subprocess
from typing import Optional


class TerminalLaunchError(Exception):
    pass


# Each entry: (binary, flag_before_bash_c)
# We always run: <binary> <flag> bash -c "<cmd>"
# so every terminal gets the same "bash -c" invocation.
_TERMINALS = [
    ("x-terminal-emulator", "--"),   # Ubuntu alternative (ptyxis, etc.)
    ("gnome-terminal", "--"),
    ("ptyxis", "--"),
    ("xterm", "-e"),
    ("konsole", "-e"),
    ("xfce4-terminal", "-e"),
    ("tilix", "-e"),
    ("kitty", None),      # kitty takes the command directly with no flag
    ("alacritty", "-e"),
]


class TerminalLauncher:
    def open(self, command: str, working_directory: Optional[str] = None) -> None:
        terminal = self._find_terminal()
        if not terminal:
            raise TerminalLaunchError(
                "No supported terminal found. Install gnome-terminal, xterm, or another terminal."
            )

        term_bin, flag = terminal

        parts: list[str] = [
            f'export PATH={shlex.quote(os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"))}',
        ]
        if working_directory:
            parts.append(f"cd {shlex.quote(working_directory)}")
        parts.append(command)
        # exec bash keeps the terminal open after the command finishes so the
        # user can see output / interact. For interactive commands like ddev ssh
        # this just means a local shell appears after the session ends.
        parts.append("exec bash")

        bash_cmd = " && ".join(parts)

        if flag is None:
            # kitty takes the program + args directly
            cmd = [term_bin, "bash", "-c", bash_cmd]
        else:
            cmd = [term_bin, flag, "bash", "-c", bash_cmd]

        try:
            subprocess.Popen(
                cmd,
                start_new_session=True,
                env=os.environ.copy(),
            )
        except Exception as e:
            raise TerminalLaunchError(f"Could not open terminal: {e}") from e

    @staticmethod
    def _find_terminal() -> Optional[tuple]:
        for name, flag in _TERMINALS:
            if shutil.which(name):
                return name, flag
        return None
