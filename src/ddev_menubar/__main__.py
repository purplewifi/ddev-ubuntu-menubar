#!/usr/bin/env python3
import sys

from gi.repository import GLib
GLib.set_prgname("ddev-menubar")
GLib.set_application_name("DDEV Menubar")

import gi
gi.require_version("Gtk", "3.0")

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
except ValueError:
    print(
        "Error: AyatanaAppIndicator3 GIR typelib not found.\n"
        "Install it with: sudo apt install gir1.2-ayatanaappindicator3-0.1",
        file=sys.stderr,
    )
    sys.exit(1)

from .ui.tray_app import TrayApp


def main() -> None:
    app = TrayApp()
    app.run()


if __name__ == "__main__":
    main()
